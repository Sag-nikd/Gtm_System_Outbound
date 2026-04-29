"""
Stage-level notifications — Slack webhook and optional SMTP email.
Reads per-stage routing from config/scheduler.json.
"""
from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from src.utils.logger import get_logger

log = get_logger(__name__)

_CONSECUTIVE_FAILURES: dict = {}
_LAST_ALERT: dict = {}


def send_stage_notification(
    stage_name: str,
    status: str,                 # "completed" | "failed"
    record_count: int,
    duration_seconds: float,
    error: Optional[str] = None,
    scheduler_cfg: Optional[dict] = None,
    retry_count: int = 0,
) -> None:
    cfg = scheduler_cfg or {}
    stage_cfg = cfg.get(stage_name, {})
    defaults = cfg.get("defaults", {})

    notify_success = stage_cfg.get("notify_on_success", defaults.get("notification_on_success", False))
    notify_failure = stage_cfg.get("notify_on_failure", defaults.get("notification_on_failure", True))

    if status == "completed" and not notify_success:
        return
    if status == "failed" and not notify_failure:
        return

    # Dedup: suppress if same stage failed with same error within last hour.
    if status == "failed" and _is_duplicate_alert(stage_name, error):
        log.debug("Suppressing duplicate failure alert for %s", stage_name)
        return

    _update_consecutive_failures(stage_name, status)
    consecutive = _CONSECUTIVE_FAILURES.get(stage_name, 0)

    message = _build_message(stage_name, status, record_count, duration_seconds, error, retry_count, consecutive, cfg)
    channel = stage_cfg.get("notify_channel", defaults.get("notify_channel", "#gtm-alerts"))

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if webhook_url:
        _send_slack(message, channel, webhook_url, mention_channel=(consecutive >= 3 and status == "failed"))
    else:
        log.info("Notification (no Slack webhook): %s", message)

    # Email for critical alerts.
    smtp_host = os.getenv("SMTP_HOST", "")
    alert_email = os.getenv("ALERT_EMAIL", "")
    if consecutive >= 3 and status == "failed" and smtp_host and alert_email:
        _send_email(
            f"[CRITICAL] GTM Pipeline: {stage_name} failed {consecutive} times",
            message,
            alert_email,
        )


def _build_message(
    stage_name: str, status: str, count: int, duration: float,
    error: Optional[str], retries: int, consecutive: int, cfg: dict,
) -> str:
    from src.scheduler.registry import STAGES
    display = STAGES.get(stage_name, {}).get("display_name", stage_name)

    if status == "completed":
        return (
            f"Stage {stage_name} ({display}) completed — "
            f"{count} records in {duration:.1f}s"
        )

    retry_info = f" after {retries} retries" if retries > 0 else ""
    consec_info = f" ({consecutive} consecutive failures)" if consecutive > 1 else ""
    err_summary = error[:120] if error else "unknown error"
    return (
        f"Stage {stage_name} ({display}) FAILED{retry_info}{consec_info} — "
        f"{err_summary}"
    )


def _send_slack(message: str, channel: str, webhook_url: str, mention_channel: bool = False) -> None:
    try:
        import urllib.request
        text = ("<!channel> " if mention_channel else "") + message
        payload = json.dumps({"text": text, "channel": channel}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        log.debug("Slack notification sent to %s", channel)
    except (OSError, ValueError) as exc:
        log.warning("Slack notification failed: %s", exc)


def _send_email(subject: str, body: str, to_email: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not smtp_host:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
            s.starttls()
            if smtp_user:
                s.login(smtp_user, smtp_pass)
            s.sendmail(from_email, [to_email], msg.as_string())
        log.debug("Email alert sent to %s", to_email)
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("Email notification failed: %s", exc)


def _update_consecutive_failures(stage_name: str, status: str) -> None:
    if status == "failed":
        _CONSECUTIVE_FAILURES[stage_name] = _CONSECUTIVE_FAILURES.get(stage_name, 0) + 1
    else:
        _CONSECUTIVE_FAILURES[stage_name] = 0


def _is_duplicate_alert(stage_name: str, error: Optional[str]) -> bool:
    import time
    key = (stage_name, error or "")
    last = _LAST_ALERT.get(key, 0)
    now = time.time()
    if now - last < 3600:  # 1 hour dedup window
        return True
    _LAST_ALERT[key] = now
    return False
