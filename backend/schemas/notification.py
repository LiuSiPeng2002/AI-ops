from pydantic import BaseModel


class TestNotificationRequest(BaseModel):
    """Request to send a test notification."""
    message: str = "AI-Ops 平台测试消息"
    msgtype: str = "text"  # text | markdown


class NotificationConfigResponse(BaseModel):
    """Current notification configuration."""
    enabled: bool
    notify_on_anomaly: bool
    notify_on_remedy: bool
    notify_on_verify_fail: bool
    notify_on_loop_exhausted: bool
    webhook_configured: bool


class NotificationConfigUpdate(BaseModel):
    """Update notification configuration."""
    enabled: bool | None = None
    notify_on_anomaly: bool | None = None
    notify_on_remedy: bool | None = None
    notify_on_verify_fail: bool | None = None
    notify_on_loop_exhausted: bool | None = None
