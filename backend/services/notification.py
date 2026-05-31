"""DingTalk robot notification service.

Supports text and markdown message types. Integrates with the AI-Ops
agent pipeline to send alerts on anomalies, remedies, and verification failures.

Rate-limited to max 20 messages/minute per DingTalk robot policy.
"""

import hashlib
import hmac
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings


class DingTalkNotifier:
    """Send notifications via DingTalk robot webhook."""

    def __init__(self):
        self.enabled = settings.dingtalk_enabled
        self.webhook = settings.dingtalk_webhook_url
        self.secret = settings.dingtalk_secret
        self._last_send: float = 0
        self._send_count: int = 0
        self._min_interval: float = 0.5  # min seconds between messages

    # ---- internal helpers ----

    def _sign(self) -> tuple[str, str]:
        """Return (timestamp, sign) for HMAC signature verification."""
        ts = str(round(time.time() * 1000))
        secret_enc = self.secret.encode("utf-8")
        string_to_sign = f"{ts}\n{self.secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(
            hmac_code.hex() if isinstance(hmac_code, bytes) else hmac_code
        )
        return ts, sign

    def _build_url(self) -> str:
        url = self.webhook
        if self.secret:
            ts, sign = self._sign()
            url = f"{url}&timestamp={ts}&sign={sign}"
        return url

    async def _post(self, payload: dict) -> bool:
        """Send payload to DingTalk webhook. Respects rate limits."""
        if not self.enabled:
            return False

        now = time.monotonic()
        # Reset counter each minute
        if now - self._last_send > 60:
            self._send_count = 0
            self._last_send = now

        # Rate limit: 20/min
        if self._send_count >= 20:
            return False

        # Minimum interval between messages
        elapsed = now - self._last_send
        if elapsed < self._min_interval and self._send_count > 0:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._build_url(), json=payload)
                self._send_count += 1
                self._last_send = time.monotonic()
                return resp.status_code == 200 and resp.json().get("errcode") == 0
        except Exception:
            return False

    # ---- public API ----

    async def send_text(self, content: str) -> bool:
        """Send a plain text message."""
        return await self._post({
            "msgtype": "text",
            "text": {"content": content},
        })

    async def send_markdown(self, title: str, text: str) -> bool:
        """Send a markdown-formatted message."""
        return await self._post({
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text,
            },
        })

    # ---- AI-Ops alert templates ----

    async def send_anomaly_alert(
        self,
        severity: str,
        summary: str,
        target: Optional[dict] = None,
    ) -> bool:
        """Send formatted anomaly detection alert."""
        if not settings.dingtalk_notify_on_anomaly:
            return False

        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
        target_str = ""
        if target:
            parts = []
            if target.get("service"):
                parts.append(f"**服务**: {target['service']}")
            if target.get("namespace"):
                parts.append(f"**命名空间**: {target['namespace']}")
            if target.get("node"):
                parts.append(f"**节点**: {target['node']}")
            if parts:
                target_str = "\n\n" + "\n".join(parts)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        title = f"AI-Ops 异常告警 [{severity.upper()}]"

        text = (
            f"## {emoji} {title}\n\n"
            f"**时间**: {now}\n"
            f"**严重程度**: {severity}\n"
            f"{target_str}\n\n"
            f"**摘要**:\n\n{summary[:500]}"
        )
        return await self.send_markdown(title, text)

    async def send_remedy_alert(
        self,
        strategy: str,
        results: list[dict],
    ) -> bool:
        """Send formatted remedy execution notification."""
        if not settings.dingtalk_notify_on_remedy:
            return False

        success_count = sum(1 for r in results if r.get("success"))
        total = len(results)
        status_emoji = "✅" if success_count == total else "⚠️"

        lines = [
            f"## {status_emoji} AI-Ops 自愈执行通知",
            "",
            f"**策略**: {strategy or '(未指定)'}",
            f"**结果**: {success_count}/{total} 成功",
            "",
            "**命令详情**:",
        ]
        for r in results:
            icon = "✅" if r.get("success") else "❌"
            cmd = r.get("command", "")[:80]
            risk = r.get("risk_level", "L0")
            lines.append(f"- {icon} [{risk}] `{cmd}`")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"\n**时间**: {now}")

        title = "AI-Ops 自愈通知"
        return await self.send_markdown(title, "\n".join(lines))

    async def send_verify_fail_alert(
        self,
        retry_count: int,
        max_retries: int,
        details: Optional[dict] = None,
    ) -> bool:
        """Send verification failure / retry alert."""
        if not settings.dingtalk_notify_on_verify_fail:
            return False

        detail_lines = ""
        if details:
            for k, v in details.items():
                detail_lines += f"- **{k}**: {v}\n"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        title = f"AI-Ops 验证失败 (重试 {retry_count}/{max_retries})"

        text = (
            f"## 🔄 {title}\n\n"
            f"**时间**: {now}\n"
            f"**重试次数**: {retry_count}/{max_retries}\n\n"
            f"{detail_lines}"
        )
        return await self.send_markdown(title, text)

    async def send_loop_exhausted_alert(
        self,
        user_input: str,
        retry_count: int,
        final_result: str = "",
    ) -> bool:
        """Send alert when self-healing loop is exhausted (max retries)."""
        if not settings.dingtalk_notify_on_loop_exhausted:
            return False

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        title = "AI-Ops 自愈循环耗尽 — 需人工介入"

        text = (
            f"## 🆘 {title}\n\n"
            f"**时间**: {now}\n"
            f"**用户请求**: {user_input[:200]}\n"
            f"**重试次数**: {retry_count} 次（已达上限）\n\n"
            f"**最后结果**:\n{final_result[:500]}\n\n"
            f"> ⚠️ 请立即人工介入处理！"
        )
        return await self.send_markdown(title, text)


# Singleton
notifier = DingTalkNotifier()
