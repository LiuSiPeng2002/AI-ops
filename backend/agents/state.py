from typing import TypedDict


class AIOpsState(TypedDict, total=False):
    # 用户输入
    user_input: str
    session_id: str

    # 路由控制
    intent_type: str          # diagnosis | change | inquiry
    target_scope: dict        # {service, namespace, node}
    flow_stage: str           # observe | diagnose | knowledge | done
    current_agent: str

    # Observe Agent 输出
    collected_data: dict      # {pods, nodes, events, logs}
    anomaly_summary: str
    anomaly_severity: str     # critical | warning | info

    # Diagnose Agent 输出
    hypotheses: list          # [{hypothesis, confidence, evidence}]
    confirmed_root_cause: dict
    historical_cases: list    # RAG 检索到的相似案例

    # Knowledge Agent 输出
    rag_context: str          # 检索到的知识片段

    # 权限控制
    user_role: str            # viewer | operator | admin | superadmin

    # 上下文延续 — 跨轮次携带
    pending_proposal: dict    # 上一轮提议的操作 {"action": str, "commands": list, "reason": str}

    # Remedy Agent 输出
    remedy_plan: dict         # {"strategy": str, "commands": [{tool, args, risk_level}]}
    remedy_results: list[dict]  # [{"command": str, "success": bool, "output": str, "attempt": int}]
    remedy_attempts: int      # 当前尝试次数 (0-based)
    remedy_needed: bool       # 是否需要进入自愈循环

    # Approval / HITL
    approval_requests: list[dict]  # [{risk_level, commands, reason, status}]
    approval_decisions: dict  # {"approved": bool, "reason": str}

    # Verify Agent 输出
    verification_results: dict  # {"health_checks": [...], "overall": "passed"|"failed"}
    verification_passed: bool

    # Loop control
    loop_complete: bool       # 自愈循环结束标志
    retry_count: int          # 总重试次数

    # 通用字段
    messages: list[dict]
    tool_results: list[dict]
    reasoning_trace: list     # DeepSeek reasoning_content 累积
    final_response: str
    error: str
    errors: list[str]
