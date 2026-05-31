import json
import uuid

from langgraph.types import Command

from agents.graph import build_graph
from agents.state import AIOpsState
from agents.tools.ops_tools import _current_role
from database import async_session
from services import audit as audit_service
from services.security import sanitize_for_audit

# Store paused graphs for resume: session_id -> (graph, config)
_paused_graphs: dict[str, tuple] = {}
# Track whether session record was created (avoid duplicate INSERT)
_audit_sessions: dict[str, bool] = {}
# Per-session sequence number
_audit_seq: dict[str, int] = {}


async def _ensure_audit_session(session_id: str, user_id: int, title: str) -> None:
    """Create an audit session record if it doesn't exist yet."""
    if session_id in _audit_sessions:
        return
    try:
        async with async_session() as db:
            await audit_service.create_session(
                db, session_id=session_id, user_id=user_id,
                title=title[:80], intent_type="inquiry",
            )
        _audit_sessions[session_id] = True
    except Exception:
        pass


async def _audit_message(session_id: str, role: str, msg_type: str, content, agent_name: str = "") -> None:
    """Persist a sanitized message to the audit trail."""
    seq = _audit_seq.get(session_id, 0) + 1
    _audit_seq[session_id] = seq
    try:
        safe = sanitize_for_audit(content)
        async with async_session() as db:
            await audit_service.append_message(
                db, session_id, role, msg_type,
                safe if isinstance(safe, dict) else {"text": str(safe)},
                agent_name=agent_name, sequence_num=seq,
            )
    except Exception:
        pass


async def _finalize_audit(session_id: str, final_status: str = "success") -> None:
    """Mark the audit session as completed and trigger consolidation."""
    try:
        async with async_session() as db:
            await audit_service.update_session_status(
                db, session_id, status="completed", final_status=final_status)
            # Trigger memory consolidation (fire-and-forget, non-blocking)
            import asyncio
            from agents.consolidation import run_consolidation_async
            session_data = await audit_service.get_session(db, session_id)
            if session_data:
                asyncio.create_task(run_consolidation_async(session_id, session_data, db))
    except Exception:
        pass


async def chat_stream_generator(
    message: str, session_id: str | None, user_id: int,
    user_role: str = "viewer", machine_config: dict | None = None,
) -> str:
    """Async generator that yields SSE-formatted strings for a chat session."""
    if not session_id:
        session_id = str(uuid.uuid4())

    _current_role.set(user_role)
    if machine_config:
        from agents.tools.ops_tools import _current_machine
        _current_machine.set(machine_config)

    await _ensure_audit_session(session_id, user_id, message)
    await _audit_message(session_id, "user", "user_input", message)

    # Restore conversation history from previous turns (for LLM context)
    prior_messages = []
    try:
        from database import async_session as _db_session
        async with _db_session() as db:
            session_data = await audit_service.get_session(db, session_id)
            if session_data and session_data.get("messages"):
                for m in session_data["messages"]:
                    if m.get("message_type") in ("user_input", "agent_response"):
                        prior_messages.append({
                            "role": "user" if m["role"] == "user" else "assistant",
                            "content": m.get("content", {}).get("text", "") if isinstance(m.get("content"), dict) else str(m.get("content", "")),
                        })
    except Exception:
        pass

    initial_state: AIOpsState = {
        "user_input": message,
        "session_id": session_id,
        "user_role": user_role,
        "final_response": "",
        "error": "",
        "errors": [],
        "messages": prior_messages,
    }

    graph = build_graph()
    config = {"configurable": {"thread_id": session_id}}
    prev_agent = None

    try:
        async for event in graph.astream(initial_state, config):
            # --- HITL: Check for interrupt ---
            if "__interrupt__" in event:
                interrupt_obj = event["__interrupt__"][0]
                interrupt_data = interrupt_obj.value if hasattr(interrupt_obj, 'value') else interrupt_obj

                _paused_graphs[session_id] = (graph, config)
                await _audit_message(session_id, "agent", "approval_required", interrupt_data)

                yield _sse_event("approval_required", {
                    "session_id": session_id,
                    "risk_level": interrupt_data.get("risk_level", "L2"),
                    "required_approver": interrupt_data.get("required_approver", "user"),
                    "commands": interrupt_data.get("commands", []),
                    "reason": interrupt_data.get("reason", ""),
                })
                yield _sse_event("graph_paused", {"session_id": session_id})
                return  # Session paused — no "done" event

            node_name = list(event.keys())[0]
            node_state = event[node_name]
            event_data = _extract_node_events(node_name, node_state, prev_agent, session_id)
            for sse_str in event_data:
                yield sse_str

            # Persist ALL agent events to audit trail
            await _audit_node_events(node_name, node_state, session_id)

            if node_name != prev_agent:
                prev_agent = node_name

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})
        yield _sse_event("done", {"session_id": session_id, "total_tokens": 0, "status": "error"})
        await _audit_message(session_id, "system", "error", str(e))
        await _finalize_audit(session_id, "failed")
        return

    await _finalize_audit(session_id, "success")
    yield _sse_event("done", {
        "session_id": session_id,
        "total_tokens": 0,
        "status": "success",
    })


async def resume_chat_stream(session_id: str, approved: bool, reason: str = "") -> str:
    """Resume a paused graph after approval decision. Yields SSE events."""
    stored = _paused_graphs.pop(session_id, None)
    if not stored:
        yield _sse_event("error", {"session_id": session_id, "message": "No paused session found"})
        return

    graph, config = stored
    resume_value = {"approved": approved, "reason": reason}
    prev_agent = None

    # Persist approval decision
    await _audit_message(session_id, "user", "approval_decision",
                         {"approved": approved, "reason": reason})

    try:
        yield _sse_event("approval_result", {
            "session_id": session_id,
            "approved": approved,
            "reason": reason,
        })

        async for event in graph.astream(Command(resume=resume_value), config):
            # Check for nested interrupts (multi-approval scenarios)
            if "__interrupt__" in event:
                interrupt_obj = event["__interrupt__"][0]
                interrupt_data = interrupt_obj.value if hasattr(interrupt_obj, 'value') else interrupt_obj
                _paused_graphs[session_id] = (graph, config)
                await _audit_message(session_id, "agent", "approval_required", interrupt_data)
                yield _sse_event("approval_required", {
                    "session_id": session_id,
                    "risk_level": interrupt_data.get("risk_level", "L2"),
                    "required_approver": interrupt_data.get("required_approver", "user"),
                    "commands": interrupt_data.get("commands", []),
                    "reason": interrupt_data.get("reason", ""),
                })
                yield _sse_event("graph_paused", {"session_id": session_id})
                return

            node_name = list(event.keys())[0]
            node_state = event[node_name]
            event_data = _extract_node_events(node_name, node_state, prev_agent, session_id)
            for sse_str in event_data:
                yield sse_str

            await _audit_node_events(node_name, node_state, session_id)

            if node_name != prev_agent:
                prev_agent = node_name

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})
        yield _sse_event("done", {"session_id": session_id, "total_tokens": 0, "status": "error"})
        await _audit_message(session_id, "system", "error", str(e))
        await _finalize_audit(session_id, "failed")
        return

    await _finalize_audit(session_id, "success")
    yield _sse_event("done", {
        "session_id": session_id,
        "total_tokens": 0,
        "status": "success",
    })


async def _audit_node_events(node_name: str, node_state: dict, session_id: str) -> None:
    """Persist all agent events from a node's state to the audit trail."""
    # Tool calls + results
    for tr in node_state.get("tool_results", []):
        await _audit_message(session_id, "agent", "tool_call",
                             {"tool": tr["tool"], "args": tr.get("args", {})},
                             agent_name=node_name)
        await _audit_message(session_id, "agent", "tool_result",
                             {"tool": tr["tool"], "result": tr.get("result", "")},
                             agent_name=node_name)

    # Anomaly
    if node_state.get("anomaly_summary"):
        await _audit_message(session_id, "agent", "anomaly_detected",
                             {"summary": node_state["anomaly_summary"],
                              "severity": node_state.get("anomaly_severity", "info")},
                             agent_name=node_name)

    # Hypotheses
    for h in node_state.get("hypotheses", []):
        await _audit_message(session_id, "agent", "hypothesis",
                             {"hypothesis": h.get("hypothesis", ""),
                              "confidence": h.get("confidence", 0),
                              "evidence": h.get("evidence", "")},
                             agent_name=node_name)

    # Root cause
    root_cause = node_state.get("confirmed_root_cause")
    if root_cause and root_cause.get("cause"):
        await _audit_message(session_id, "agent", "root_cause",
                             {"cause": root_cause.get("cause", ""),
                              "confidence": root_cause.get("confidence", 0)},
                             agent_name=node_name)

    # Remedy plan
    remedy_plan = node_state.get("remedy_plan")
    if remedy_plan and remedy_plan.get("commands"):
        await _audit_message(session_id, "agent", "remedy_plan",
                             {"strategy": remedy_plan.get("strategy", ""),
                              "commands": remedy_plan.get("commands", [])},
                             agent_name=node_name)

    # Remedy execution results
    for rr in node_state.get("remedy_results", []):
        await _audit_message(session_id, "agent", "remedy_result",
                             {"command": rr.get("command", ""),
                              "success": rr.get("success", False),
                              "output": rr.get("output", ""),
                              "attempt": rr.get("attempt", 0)},
                             agent_name=node_name)

    # Verification checks
    for vc in node_state.get("verification_results", {}).get("health_checks", []):
        await _audit_message(session_id, "agent", "verification_status",
                             vc, agent_name=node_name)

    # Retry attempts
    retry = node_state.get("retry_count", 0)
    if retry > 0:
        await _audit_message(session_id, "agent", "retry_attempt",
                             {"attempt": retry, "max_attempts": 3,
                              "reason": "Verification failed, retrying"},
                             agent_name=node_name)

    # Agent reasoning trace
    for rt in node_state.get("reasoning_trace", []):
        if rt.get("content"):
            await _audit_message(session_id, "agent", "agent_reasoning",
                                 {"content": rt["content"]},
                                 agent_name=rt.get("agent", node_name))

    # Agent final response
    if node_state.get("final_response"):
        await _audit_message(session_id, "agent", "agent_response",
                             node_state["final_response"], agent_name=node_name)

    # RAG context
    rag = node_state.get("rag_context")
    if rag:
        await _audit_message(session_id, "agent", "rag_context",
                             {"content": rag[:1000]}, agent_name=node_name)


def _extract_node_events(node_name: str, node_state: dict, prev_agent: str | None, session_id: str) -> list[str]:
    """Extract all SSE events from a node's state output."""
    events = []

    # Agent active indicator
    if node_name != prev_agent:
        events.append(_sse_event("agent_active", {
            "agent": node_name,
            "session_id": session_id,
        }))

    # Reasoning trace
    reasoning_trace = node_state.get("reasoning_trace", [])
    for rt in reasoning_trace:
        if rt.get("content"):
            events.append(_sse_event("agent_reasoning", {
                "agent": rt.get("agent", node_name),
                "content": rt["content"],
            }))

    # Tool calls and results
    tool_results = node_state.get("tool_results", [])
    for tr in tool_results:
        events.append(_sse_event("tool_call", {"tool": tr["tool"], "args": tr["args"]}))
        events.append(_sse_event("tool_result", {"tool": tr["tool"], "result": tr["result"]}))

    # Anomaly detection
    if node_state.get("anomaly_summary") and node_state.get("anomaly_severity"):
        events.append(_sse_event("anomaly_detected", {
            "severity": node_state["anomaly_severity"],
            "summary": node_state["anomaly_summary"][:500],
        }))

    # Hypotheses
    for h in node_state.get("hypotheses", []):
        events.append(_sse_event("hypothesis", {
            "hypothesis": h.get("hypothesis", ""),
            "confidence": h.get("confidence", 0),
            "evidence": h.get("evidence", ""),
        }))

    # Root cause
    root_cause = node_state.get("confirmed_root_cause")
    if root_cause and root_cause.get("cause"):
        events.append(_sse_event("root_cause", {
            "cause": root_cause.get("cause", ""),
            "confidence": root_cause.get("confidence", 0),
        }))

    # RAG context
    rag_context = node_state.get("rag_context")
    if rag_context:
        events.append(_sse_event("rag_context", {"content": rag_context[:1000]}))

    # Remedy plan
    remedy_plan = node_state.get("remedy_plan")
    if remedy_plan and remedy_plan.get("commands"):
        events.append(_sse_event("remedy_plan", {
            "strategy": remedy_plan.get("strategy", ""),
            "commands": [
                {"tool": c["tool"], "command": c["args"].get("command", ""), "risk_level": c.get("risk_level", "L0")}
                for c in remedy_plan.get("commands", [])
            ],
        }))

    # Remedy executing & results
    for rr in node_state.get("remedy_results", []):
        events.append(_sse_event("remedy_executing", {
            "command": rr.get("command", ""),
            "risk_level": rr.get("risk_level", "L0"),
            "attempt": rr.get("attempt", 0),
        }))
        events.append(_sse_event("remedy_result", {
            "command": rr.get("command", ""),
            "success": rr.get("success", False),
            "output": rr.get("output", ""),
        }))

    # Verification
    for vc in node_state.get("verification_results", {}).get("health_checks", []):
        events.append(_sse_event("verification_status", vc))

    # Retry
    retry = node_state.get("retry_count", 0)
    if retry > 0:
        events.append(_sse_event("retry_attempt", {
            "attempt": retry,
            "max_attempts": 3,
            "reason": "Verification failed, retrying with adjusted strategy",
        }))

    # Agent response
    if node_state.get("final_response"):
        events.append(_sse_event("agent_response", {
            "agent": node_name,
            "content": node_state["final_response"],
        }))

    return events


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
