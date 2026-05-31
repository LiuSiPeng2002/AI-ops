# CLAUDE.md — AI-Ops Platform v2.0

> Multi-agent self-healing Kubernetes operations platform.
> 7 AI agents, RBAC × risk classifier, HITL approval, DingTalk alerts, bilingual UI.

## Quick context

- **Stack**: FastAPI (Python 3.11) + LangGraph/LangChain + Vue 3 + MySQL + ChromaDB
- **LLM**: DeepSeek v4-pro via OpenAI-compatible API
- **Embedding**: Ollama + qwen3-embedding:0.6b (local)
- **Entry point**: `backend/main.py` → `backend/agents/graph.py` (LangGraph state machine)
- **Frontend entry**: `frontend/src/main.js` → Vue Router → 11 pages

## Project structure

```
backend/agents/       AI agents (LangGraph nodes)
backend/api/          FastAPI routers (15 modules, 31+ endpoints)
backend/models/       SQLAlchemy models (User, Session/Message, Machine)
backend/services/     Business logic (audit, scheduler, notification, security, circuit_breaker)
backend/schemas/      Pydantic request/response models
backend/core/         Security (JWT+bcrypt) + dependency injection
frontend/src/         Vue 3 SPA — 11 views, 6 components, 2 stores, 2 i18n locales
helm/aiops/           Kubernetes Helm chart (6 templates)
```

## Architecture patterns

### Agent pipeline (LangGraph StateGraph)
```
orchestrator → observe → diagnose → remedy → verify → orchestrator_final
                    ↑                        │
                    └──── retry (≤3) ────────┘
```
- State: `AIOpsState` (TypedDict) in `agents/state.py`
- Router: `_route_by_intent`, `_route_after_observe`, `_route_after_diagnose`, `_route_after_remedy`, `_route_after_verify`
- Checkpointer: `MemorySaver` keyed by `thread_id=session_id`

### Intent routing rules
- `conversation` → skip observe, go to `orchestrator_final` (greetings, meta-questions)
- `diagnosis` → observe → diagnose → (root_cause) → remedy → verify → final
- `change` → observe → remedy → verify → final (or skip observe if pending proposal / direct command)
- `inquiry` → observe → knowledge → final
- Direct Linux commands (bash/systemctl/df/...) → remedy → skip verify → final
- Direct K8s commands (kubectl scale/delete/...) → remedy → light verify → final

### HITL (Human-in-the-Loop)
- L2+ risk commands: `remedy_node` calls `interrupt()` → SSE `approval_required` → frontend shows approval card
- User approves/rejects via `POST /api/chat/resume` → `Command(resume={approved: bool})`
- Context continuity: `pending_proposal` in state preserves the proposed action across turns

### RBAC × Risk classifier
- 4 roles: `viewer`, `operator`, `admin`, `superadmin`
- L0-L4 risk levels in `agents/tools/risk_classifier.py` (deterministic, 86 tests)
- View layer: `_validate_kubectl` / `_validate_linux` in `ops_tools.py`
- Execution layer: `_current_role` ContextVar propagated through request chain
- Auto-approval matrix: admin auto-approves L2, superadmin auto-approves L3

### Multi-machine SSH
- Machines stored in MySQL `machines` table
- `_current_machine` ContextVar for dynamic SSH routing
- Frontend selects machine → sends `machine_id` → backend loads credentials from DB
- Password NEVER sent to frontend (API response excludes it)
- Falls back to `settings.k8s_master_*` if no machine selected

### Audit persistence
- `chat_service.py` → `_audit_node_events()` audits ALL event types (tool_call, tool_result, anomaly, hypothesis, root_cause, remedy_plan, remedy_result, verification, retry, agent_reasoning, agent_response)
- `services/security.py` → `sanitize_for_audit()` masks tokens/passwords before storage
- `services/consolidation.py` → auto-generates knowledge cases from completed sessions

## Key files to know

| File | Purpose |
|------|---------|
| `agents/graph.py` | LangGraph workflow definition + all routing functions |
| `agents/orchestrator.py` | Intent classification (ROUTER_PROMPT) + final synthesis (FINAL_PROMPT) |
| `agents/remedy.py` | Repair plan generation + HITL interrupt + command execution |
| `agents/verify.py` | Post-repair verification + retry decision |
| `agents/tools/ops_tools.py` | `kubectl_exec`, `linux_exec`, `prometheus_query` + security validators |
| `agents/tools/risk_classifier.py` | L0-L4 deterministic classifier + auto-approval logic |
| `services/chat_service.py` | SSE streaming generator + HITL resume + audit sync |
| `services/scheduler.py` | 5 periodic inspection tasks with DingTalk alerts |
| `services/security.py` | Sensitive data masking (JWT, API keys, passwords, private keys) |
| `services/circuit_breaker.py` | Sliding-window circuit breaker (5 failures = open, 60s reset) |
| `config.py` | All settings (DB, LLM, SSH, DingTalk, performance, security) |

## Frontend patterns

- **Stores**: Pinia — `auth.js` (token/user) + `chat.js` (SSE stream, agent events, abort controller)
- **SSE events**: 18 event types handled in `chat.js → handleSSEEvent()`
- **11 pages**: Chat, Login, Dashboard, Audit, Knowledge, Inspection, Users, Topology, Terminal, Machines, Profile
- **i18n**: vue-i18n with `zh-CN.js` and `en-US.js` (~180 keys each), localStorage persistence
- **Markdown**: `MarkdownRenderer.vue` (marked + highlight.js for code blocks)
- **Terminal**: xterm.js + WebSocket (`/api/terminal/ws`)
- **DAG**: `DagViewer.vue` (SVG-based agent decision path graph)

## Running the project

```bash
# Backend (needs MySQL + Ollama running)
cd backend && ./venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend dev server
cd frontend && npx vite --host 0.0.0.0 --port 5173

# Docker compose (all services)
docker-compose up -d --build
```

## Common gotchas

- **Windows paths**: Use forward slashes `E:/Project-VibeCoding/...` in bash
- **Kill stuck processes**: `cmd //c "taskkill /F /IM python.exe"` on Windows
- **DB init timeout**: `connect_args={"connect_timeout": 10}` breaks aiomysql — never use it
- **ContextVar in StreamingResponse**: ContextVars set before `StreamingResponse` may not propagate into the async generator. Pass values as function arguments instead (see `machine_config` pattern)
- **grep not allowed**: Added `grep` to `LINUX_SAFE_COMMANDS` — it was only in `PIPE_SAFE_COMMANDS`
- **sed verification**: Always re-read file after `sed -i` to confirm changes took effect
- **Script execution**: Must use `bash /path/script.sh`, not direct path `/path/script.sh`
- **Duplicate commands**: Remedy prompt now forbids generating duplicate commands
- **.env loading**: `config.py` uses `pydantic_settings.BaseSettings` with `env_file=".env"`

## PRD phases completed

- ✅ Phase 1: Core framework + auth + SSE chat
- ✅ Phase 2: Multi-agent (Observe, Diagnose, Knowledge) + RBAC tools
- ✅ Phase 3: Self-healing loop + HITL approval (Remedy, Verify) + risk classifier
- ✅ Phase 4: Enterprise features (DingTalk, dashboard, audit, knowledge, inspections, DAG, i18n)
- ✅ Phase 5: Production hardening (Docker, Helm, security masking, circuit breaker, deploy docs)
- ✅ Phase 6: Advanced features (consolidation agent, user management, Prometheus, terminal, topology)
