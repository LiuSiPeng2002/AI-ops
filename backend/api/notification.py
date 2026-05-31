from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from models.user import User
from schemas.notification import (
    NotificationConfigResponse,
    NotificationConfigUpdate,
    TestNotificationRequest,
)
from services.notification import notifier

router = APIRouter(prefix="/api/notify", tags=["notification"])


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_notification(
    request: TestNotificationRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a test notification to verify DingTalk integration."""
    if not notifier.enabled:
        raise HTTPException(status_code=400, detail="DingTalk notification is disabled")

    if request.msgtype == "markdown":
        ok = await notifier.send_markdown("测试通知", request.message)
    else:
        ok = await notifier.send_text(request.message)

    if ok:
        return {"status": "ok", "message": "Notification sent"}
    return {"status": "error", "message": "Failed to send notification"}


@router.get("/config", response_model=NotificationConfigResponse)
async def get_config(current_user: User = Depends(get_current_user)):
    """Get current notification configuration."""
    from config import settings

    return {
        "enabled": settings.dingtalk_enabled,
        "notify_on_anomaly": settings.dingtalk_notify_on_anomaly,
        "notify_on_remedy": settings.dingtalk_notify_on_remedy,
        "notify_on_verify_fail": settings.dingtalk_notify_on_verify_fail,
        "notify_on_loop_exhausted": settings.dingtalk_notify_on_loop_exhausted,
        "webhook_configured": bool(settings.dingtalk_webhook_url),
    }


@router.put("/config")
async def update_config(
    update: NotificationConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update notification configuration (runtime only, resets on restart)."""
    from config import settings

    if update.enabled is not None:
        settings.dingtalk_enabled = update.enabled
    if update.notify_on_anomaly is not None:
        settings.dingtalk_notify_on_anomaly = update.notify_on_anomaly
    if update.notify_on_remedy is not None:
        settings.dingtalk_notify_on_remedy = update.notify_on_remedy
    if update.notify_on_verify_fail is not None:
        settings.dingtalk_notify_on_verify_fail = update.notify_on_verify_fail
    if update.notify_on_loop_exhausted is not None:
        settings.dingtalk_notify_on_loop_exhausted = update.notify_on_loop_exhausted

    # Sync notifier state
    notifier.enabled = settings.dingtalk_enabled

    return {"status": "ok"}
