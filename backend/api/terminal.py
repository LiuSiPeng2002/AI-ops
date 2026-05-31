"""Web Terminal — WebSocket-based interactive shell for K8s/Linux commands."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.tools.ops_tools import kubectl_exec, linux_exec, _current_role
from core.deps import get_user_from_token_ws

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


@router.websocket("/ws")
async def terminal_ws(websocket: WebSocket):
    """WebSocket endpoint for interactive command execution.

    Client sends: {"command": "kubectl get pods", "type": "kubectl" | "linux"}
    Server replies: {"output": "...", "error": "..." | null}
    """
    await websocket.accept()

    # Authenticate via token query param
    token = websocket.query_params.get("token", "")
    user = await get_user_from_token_ws(token)
    if not user:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return

    _current_role.set(user.role)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            command = msg.get("command", "").strip()
            cmd_type = msg.get("type", "linux")

            if not command:
                await websocket.send_json({"error": "Empty command", "output": ""})
                continue

            # Execute in thread pool to avoid blocking event loop
            try:
                if cmd_type == "kubectl":
                    output = await asyncio.to_thread(
                        lambda: kubectl_exec.invoke({"command": command})
                    )
                else:
                    output = await asyncio.to_thread(
                        lambda: linux_exec.invoke({"command": command})
                    )
                if output.startswith("ERROR") or output.startswith("SSH_ERROR"):
                    await websocket.send_json({"error": output, "output": ""})
                else:
                    await websocket.send_json({"error": None, "output": output})
            except Exception as exc:
                await websocket.send_json({"error": str(exc), "output": ""})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
