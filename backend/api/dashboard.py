"""Dashboard API: cluster health, agent status, and platform statistics."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from database import get_db
from models.session import Session
from models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level platform overview stats."""
    # Session stats
    total_sessions = (await db.execute(select(func.count()).select_from(Session))).scalar() or 0
    active_sessions = (await db.execute(
        select(func.count()).where(Session.status == "active")
    )).scalar() or 0

    success = (await db.execute(
        select(func.count()).where(Session.final_status == "success")
    )).scalar() or 0
    failed = (await db.execute(
        select(func.count()).where(Session.final_status == "failed")
    )).scalar() or 0
    escalated = (await db.execute(
        select(func.count()).where(Session.final_status == "escalated")
    )).scalar() or 0

    # Intent breakdown
    by_intent = {}
    rows = (await db.execute(
        select(Session.intent_type, func.count()).group_by(Session.intent_type)
    )).all()
    for intent, cnt in rows:
        by_intent[intent] = cnt

    # Avg attempts
    avg_attempts = (await db.execute(
        select(func.avg(Session.total_attempts))
    )).scalar() or 0

    return {
        "sessions": {
            "total": total_sessions,
            "active": active_sessions,
            "success": success,
            "failed": failed,
            "escalated": escalated,
        },
        "by_intent": by_intent,
        "avg_attempts": round(float(avg_attempts), 1),
    }


@router.get("/cluster")
async def get_cluster_health(
    current_user: User = Depends(get_current_user),
):
    """Get real-time cluster health snapshot."""
    from agents.tools.ops_tools import kubectl_exec, linux_exec, _current_role

    _current_role.set(current_user.role)

    health = {"k8s": {}, "system": {}}

    # K8s node status
    try:
        nodes = kubectl_exec.invoke({"command": "get nodes -o wide"})
        healthy_nodes = nodes.count("Ready") if "Ready" in nodes else 0
        health["k8s"]["nodes"] = nodes
        health["k8s"]["healthy"] = healthy_nodes > 0
    except Exception:
        health["k8s"]["error"] = "Failed to query nodes"

    # Pod status
    try:
        pods = kubectl_exec.invoke({"command": "get pods --all-namespaces --field-selector=status.phase!=Running,status.phase!=Succeeded"})
        health["k8s"]["problem_pods"] = pods if pods and "No resources" not in pods else "None"
    except Exception:
        health["k8s"]["problem_pods"] = "Query failed"

    # System resource
    try:
        health["system"]["disk"] = linux_exec.invoke({"command": "df -h / | tail -1"})
        health["system"]["memory"] = linux_exec.invoke({"command": "free -m | head -2"})
        health["system"]["load"] = linux_exec.invoke({"command": "uptime"})
    except Exception:
        health["system"]["error"] = "System query failed"

    return health


@router.get("/agent-status")
async def get_agent_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get per-agent activity statistics."""
    from models.session import Message

    agents = ["orchestrator", "observe", "diagnose", "knowledge", "remedy", "verify"]
    status = []

    for agent in agents:
        count = (await db.execute(
            select(func.count()).where(Message.agent_name == agent)
        )).scalar() or 0
        status.append({"agent": agent, "message_count": count, "active": count > 0})

    # Recent sessions (last 10)
    recent = (await db.execute(
        select(Session).order_by(Session.started_at.desc()).limit(10)
    )).scalars().all()

    return {
        "agents": status,
        "recent_sessions": [
            {
                "id": s.id,
                "title": s.title,
                "intent_type": s.intent_type,
                "status": s.status,
                "final_status": s.final_status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in recent
        ],
    }
