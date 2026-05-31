"""Verify Agent: post-repair verification.

Checks Pod status, Deployment health, service endpoints, and recent events
after a repair action. Compares pre/post state to determine if the repair
was successful or if a retry is needed.
"""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import settings
from services.notification import notifier

from agents.state import AIOpsState
from agents.tools.ops_tools import OPS_TOOLS
from config import settings

VERIFY_PROMPT = """You are the Verify Agent for K8s operations. Your job is to verify that repair actions succeeded.

## CRITICAL: Understand the semantics of the operation
- DELETE (rm, kubectl delete, etc.): the target should NOT exist after deletion.
  "No such file or directory" IS SUCCESS for a delete operation.
  "cannot remove ... No such file" on second attempt ALSO means success (already gone).
  If `ls` returns "No such file or directory" after a delete → verification PASSED.
- CREATE (touch, mkdir, echo >, kubectl apply): the target should exist after creation.
- MODIFY (sed, chmod, kubectl scale): the target should have the new state.
- EXECUTE (bash, python3, curl): check exit code/output, not the entire cluster.
- RESTART (systemctl restart, rollout restart): check the service is running after.

## CRITICAL: Scope your checks to what was actually changed
- Linux commands: verify only the specific file/process/service. Do NOT run kubectl.
- K8s commands: check only the affected resource. NEVER "get pods --all-namespaces".
- Keep it to 1–2 targeted checks.
- If the first verification check already shows the operation clearly succeeded (e.g., file deleted),
  mark verification as PASSED immediately. Do NOT run a second identical check.
- An error message that CONFIRMS the desired state (e.g., "No such file" after rm)
  counts as PASSED verification, not failed.
4. Determine if repair was successful.

## Rules
- Be thorough — check pod STATUS, RESTARTS, AGE, and READY counts.
- If pods are Running but health checks fail, that's still a FAIL.
- If any check fails, clearly state what failed and what needs to be different.
- Generate SIMPLE, SINGLE commands. No shell constructs.

## Output
After verification, respond in this format:
VERIFICATION_RESULT: passed | failed
FAILED_CHECKS: <list of failed items, or "none" if all passed>
DETAILS: <brief summary of verification findings>
"""

llm = ChatOpenAI(
    model=settings.model_name,
    openai_api_key=settings.openai_api_key,
    openai_api_base=settings.openai_base_url,
    temperature=0.2,
)
llm_with_tools = llm.bind_tools(OPS_TOOLS)


def _extract_reasoning(response) -> str:
    return response.additional_kwargs.get("reasoning_content", "")


async def verify_node(state: AIOpsState) -> dict:
    """Verify Agent: post-repair verification of cluster state."""
    user_input = state["user_input"]
    target = state.get("target_scope", {})
    root_cause = state.get("confirmed_root_cause", {})
    remedy_results = state.get("remedy_results", [])

    # Build context
    context_parts = [f"Original request: {user_input}"]
    if target:
        context_parts.append(f"Target: {target}")
    if root_cause:
        context_parts.append(f"Root cause addressed: {root_cause.get('cause', 'unknown')}")
    if remedy_results:
        context_parts.append("## Repair Actions Taken")
        for rr in remedy_results:
            status = "SUCCESS" if rr.get("success") else "FAILED"
            context_parts.append(f"- [{status}] {rr.get('command', '')}: {rr.get('output', '')[:300]}")

    prompt = f"{VERIFY_PROMPT}\n\n{'  '.join(context_parts)}"

    chat_messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Verify the repair was successful. Collect current cluster state and compare."),
    ]

    response = await llm_with_tools.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

    tool_results = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_fn = next((t for t in OPS_TOOLS if t.name == tool_name), None)
            if tool_fn:
                try:
                    result = tool_fn.invoke(tool_args)
                    tool_results.append({"tool": tool_name, "args": tool_args, "result": str(result)})
                except Exception as e:
                    tool_results.append({"tool": tool_name, "args": tool_args, "result": f"Error: {e}"})

    # ---- Pre-check: detect delete success without LLM analysis ----
    # If all remedy actions were deletes AND verify checks say "No such file",
    # that means the delete succeeded. Skip LLM analysis, mark as passed.
    all_remedy_deletes = all(
        "rm " in rr.get("command", "") or "delete " in rr.get("command", "")
        for rr in remedy_results
    ) if remedy_results else False

    delete_success_indicators = [
        "No such file or directory", "not found", "cannot remove",
        "not found", "NotFound", "does not exist",
    ]
    all_verify_confirm_delete = all(
        any(ind in tr["result"] for ind in delete_success_indicators)
        for tr in tool_results
    ) if tool_results else False

    if all_remedy_deletes and all_verify_confirm_delete and tool_results:
        verification_passed = True
        analysis_text = "DELETE OPERATION SUCCESS: target files no longer exist (verified by No such file or directory)."
    else:
        # Analyze verification data
        analysis_prompt = [SystemMessage(content=VERIFY_PROMPT)]
        for tr in tool_results:
            analysis_prompt.append(HumanMessage(
                content=f"Tool [{tr['tool']}] with args {tr['args']} returned:\n{tr['result'][:1500]}"
            ))
        analysis_prompt.append(HumanMessage(
            content="Analyze the verification data. Output:\n"
                    "VERIFICATION_RESULT: passed | failed\n"
                    "FAILED_CHECKS: <list or 'none'>\n"
                    "DETAILS: <summary>"
        ))

        analysis_response = await llm.ainvoke(analysis_prompt)
        analysis_text = analysis_response.content

        # Parse result
        verification_passed = "VERIFICATION_RESULT: passed" in analysis_text

    # Build structured results
    health_checks = []
    for tr in tool_results:
        result_lower = tr["result"].lower()
        is_delete_confirm = any(ind.lower() in result_lower for ind in delete_success_indicators)
        if is_delete_confirm and all_remedy_deletes:
            status = "passed"
        elif "error" in result_lower and not is_delete_confirm:
            status = "warning"
        else:
            status = "passed"
        health_checks.append({
            "check_type": f"{tr['tool']}({tr['args'].get('command', '')[:50]})",
            "status": status,
            "detail": tr["result"][:300],
        })

    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "verify", "content": reasoning})

    retry_count = state.get("retry_count", 0)
    new_retry_count = retry_count + (0 if verification_passed else 1)

    # Fire DingTalk notification on verify fail or loop exhaustion
    if not verification_passed:
        max_retries = 3
        if new_retry_count >= max_retries:
            asyncio.create_task(notifier.send_loop_exhausted_alert(
                state.get("user_input", ""), new_retry_count, analysis_text
            ))
        else:
            asyncio.create_task(notifier.send_verify_fail_alert(
                new_retry_count, max_retries, {"details": analysis_text[:500]}
            ))

    return {
        "verification_results": {
            "health_checks": health_checks,
            "overall": "passed" if verification_passed else "failed",
            "details": analysis_text[:1000],
        },
        "verification_passed": verification_passed,
        "loop_complete": verification_passed or retry_count >= 2,
        "retry_count": new_retry_count,
        "current_agent": "verify",
        "flow_stage": "verify",
        "reasoning_trace": trace,
        "tool_results": tool_results,
    }
