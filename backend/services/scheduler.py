"""Lightweight background scheduler for periodic cluster inspections.

Uses asyncio tasks (no external deps like Celery). Each inspection task
runs on a configurable interval, collects cluster health data, and can
trigger auto-remediation for known issues.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from agents.tools.ops_tools import kubectl_exec, linux_exec, _current_role

# Default inspection tasks — commands MUST be simple (no shell metacharacters)
# because the scheduler validates through the same RBAC pipe as user commands.
DEFAULT_TASKS = [
    {
        "id": "pod-health",
        "name": "Pod 健康检查",
        "enabled": True,
        "interval_minutes": 30,
        "tool": "kubectl_exec",
        "command": "get pods --all-namespaces",
        "alert_on": "CrashLoopBackOff|ImagePullBackOff|Pending|Error|Unknown",
    },
    {
        "id": "node-health",
        "name": "节点资源检查",
        "enabled": True,
        "interval_minutes": 15,
        "tool": "kubectl_exec",
        "command": "get nodes -o wide",
        "alert_on": "NotReady|SchedulingDisabled",
    },
    {
        "id": "disk-check",
        "name": "磁盘空间检查",
        "enabled": True,
        "interval_minutes": 60,
        "tool": "linux_exec",
        "command": "df -h",
        "alert_on": "100%|[89][0-9]%",
    },
    {
        "id": "memory-check",
        "name": "内存使用检查",
        "enabled": True,
        "interval_minutes": 30,
        "tool": "linux_exec",
        "command": "free -m",
        "alert_on": "",
    },
    {
        "id": "service-status",
        "name": "关键服务状态",
        "enabled": True,
        "interval_minutes": 60,
        "tool": "linux_exec",
        "command": "systemctl is-active docker",
        "alert_on": "inactive|failed|unknown",
    },
]


class InspectionScheduler:
    """Manages periodic cluster inspection tasks."""

    def __init__(self):
        self._tasks: list[dict] = []
        self._results: list[dict] = []  # Last 100 results
        self._running = False
        self._task_handles: dict[str, asyncio.Task] = {}

    @property
    def tasks(self) -> list[dict]:
        """Return merged task list: _tasks overrides DEFAULT_TASKS, both preserved."""
        if not self._tasks:
            return DEFAULT_TASKS
        # Build merged list: modified defaults + any custom tasks
        modified_ids = {t["id"] for t in self._tasks}
        result = []
        for dt in DEFAULT_TASKS:
            if dt["id"] in modified_ids:
                # Use the mutable copy (preserves enabled/interval changes)
                result.append(next(t for t in self._tasks if t["id"] == dt["id"]))
            else:
                result.append(dt)
        # Include custom tasks not in defaults
        default_ids = {d["id"] for d in DEFAULT_TASKS}
        for t in self._tasks:
            if t["id"] not in default_ids:
                result.append(t)
        return result

    @property
    def results(self) -> list[dict]:
        return self._results[-100:]

    async def start(self) -> None:
        """Start all enabled inspection tasks."""
        if self._running:
            return
        self._running = True
        for task in self.tasks:
            if task.get("enabled", True):
                self._schedule_task(task)

    async def stop(self) -> None:
        """Stop all inspection tasks."""
        self._running = False
        for handle in self._task_handles.values():
            handle.cancel()
        self._task_handles.clear()

    def _schedule_task(self, task: dict) -> None:
        """Schedule a single inspection task to run periodically."""
        async def _run():
            while self._running:
                try:
                    result = await self._execute(task)
                    self._results.append(result)
                    if len(self._results) > 100:
                        self._results = self._results[-100:]

                    # Trigger alert if needed
                    if result.get("alert"):
                        await self._send_alert(task, result)
                except Exception:
                    pass
                await asyncio.sleep(task.get("interval_minutes", 30) * 60)

        self._task_handles[task["id"]] = asyncio.create_task(_run())

    async def _execute(self, task: dict) -> dict:
        """Execute a single inspection and return result.

        Sets _current_role to 'admin' before execution — the scheduler is a
        trusted system component that needs elevated access for inspection
        commands (e.g. pipes and redirects that viewer/operator can't use).
        """
        tool = task["tool"]
        command = task["command"]
        token = _current_role.set("admin")

        try:
            if tool == "kubectl_exec":
                output = kubectl_exec.invoke({"command": command})
            else:
                output = linux_exec.invoke({"command": command})

            # Check if output matches alert pattern
            alert = False
            alert_pattern = task.get("alert_on", "")
            if alert_pattern:
                import re
                alert = bool(re.search(alert_pattern, output))
        except Exception as exc:
            output = f"Error: {exc}"
            alert = True
        finally:
            _current_role.reset(token)

        return {
            "task_id": task["id"],
            "name": task["name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "output": output[:2000],
            "alert": alert,
        }

    async def _send_alert(self, task: dict, result: dict) -> None:
        """Send DingTalk alert for inspection findings."""
        try:
            from services.notification import notifier
            await notifier.send_markdown(
                f"巡检告警: {task['name']}",
                f"## 🔍 {task['name']}\n\n"
                f"**时间**: {result['timestamp']}\n"
                f"**任务**: {task['id']}\n\n"
                f"**输出**:\n```\n{result['output'][:800]}\n```"
            )
        except Exception:
            pass

    async def run_once(self, task_id: str) -> Optional[dict]:
        """Run a specific task once (for manual trigger)."""
        for task in self.tasks:
            if task["id"] == task_id:
                result = await self._execute(task)
                self._results.append(result)
                return result
        return None


# Singleton
scheduler = InspectionScheduler()
