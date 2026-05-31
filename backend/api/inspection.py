"""Inspection API: manage periodic inspection tasks and manual triggers."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.deps import get_current_user
from models.user import User
from services.scheduler import DEFAULT_TASKS, scheduler

router = APIRouter(prefix="/api/inspection", tags=["inspection"])


class InspectionTaskUpdate(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    alert_on: str | None = None
    command: str | None = None


class InspectionConfig(BaseModel):
    tasks: list[dict]
    running: bool


@router.get("/tasks")
async def get_tasks(current_user: User = Depends(get_current_user)):
    """List all inspection tasks with their current status."""
    result = []
    for t in scheduler.tasks:
        result.append({
            "id": t["id"],
            "name": t["name"],
            "enabled": t.get("enabled", True),
            "interval_minutes": t.get("interval_minutes", 30),
            "tool": t["tool"],
            "command": t["command"],
            "alert_on": t.get("alert_on", ""),
        })
    return {"tasks": result, "running": scheduler._running}


@router.get("/results")
async def get_results(
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get recent inspection results."""
    results = scheduler.results[-limit:]
    return {"results": list(reversed(results)), "total": len(results)}


@router.post("/run/{task_id}")
async def run_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a specific inspection task."""
    result = await scheduler.run_once(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return result


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    update: InspectionTaskUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update an inspection task configuration."""
    # Search the merged task list
    task = next((t for t in scheduler.tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Ensure task is in the mutable _tasks list (copy from defaults if needed)
    if task not in scheduler._tasks:
        new_task = dict(task)
        scheduler._tasks.append(new_task)
        task = new_task

    # Apply updates
    if update.enabled is not None:
        task["enabled"] = update.enabled
    if update.interval_minutes is not None:
        task["interval_minutes"] = update.interval_minutes
    if update.alert_on is not None:
        task["alert_on"] = update.alert_on
    if update.command is not None:
        task["command"] = update.command

    return {"status": "ok"}


@router.post("/start")
async def start_scheduler(current_user: User = Depends(get_current_user)):
    """Start the inspection scheduler."""
    await scheduler.start()
    return {"status": "ok", "running": scheduler._running}


@router.post("/stop")
async def stop_scheduler(current_user: User = Depends(get_current_user)):
    """Stop the inspection scheduler."""
    await scheduler.stop()
    return {"status": "ok", "running": scheduler._running}
