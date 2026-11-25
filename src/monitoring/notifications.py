"""Optional Stage 5 monitoring event notification hooks."""

from __future__ import annotations

import json
import time
from typing import Dict, Optional

from config.settings import CREDENTIALS
from src.data.db import get_db


def notify_monitoring_event(
    event_type: str,
    status: str,
    message: str,
    subject_id: Optional[str] = None,
    payload: Optional[Dict] = None,
    notify_external: bool = False,
) -> Dict:
    db = get_db()
    event_id = db.record_monitoring_event(
        event_type,
        status,
        message,
        subject_id=subject_id,
        payload=payload,
    )
    external = {"telegram": False, "email": False}
    details = {"telegram": "NOT_ATTEMPTED", "email": "NOT_ATTEMPTED"}

    if not notify_external:
        return {
            "event_id": event_id,
            "external": external,
            "verified": False,
        }

    if CREDENTIALS.telegram_bot_token and CREDENTIALS.telegram_chat_id:
        for attempt in range(1, 4):
            try:
                import requests
                response = requests.post(
                    f"https://api.telegram.org/bot{CREDENTIALS.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": CREDENTIALS.telegram_chat_id,
                        "text": f"[{status}] {event_type}: {message}",
                    },
                    timeout=10,
                )
                if response.ok:
                    external["telegram"] = True
                    details["telegram"] = "DELIVERED"
                    break
                details["telegram"] = f"HTTP_{response.status_code}"
            except Exception as exc:
                details["telegram"] = f"ERROR_{type(exc).__name__}"
            if attempt < 3:
                time.sleep(2 ** attempt)
    else:
        details["telegram"] = "NOT_CONFIGURED"

    if (
        CREDENTIALS.smtp_username
        and CREDENTIALS.smtp_password
        and CREDENTIALS.alert_email_to
    ):
        for attempt in range(1, 4):
            try:
                import smtplib
                from email.mime.text import MIMEText

                message_text = MIMEText(
                    f"Event: {event_type}\nStatus: {status}\n"
                    f"Subject: {subject_id or 'N/A'}\n\n{message}",
                )
                message_text["Subject"] = f"[Tirumala Monitor] {event_type}: {status}"
                message_text["From"] = CREDENTIALS.smtp_username
                message_text["To"] = CREDENTIALS.alert_email_to
                with smtplib.SMTP(CREDENTIALS.smtp_host, CREDENTIALS.smtp_port) as server:
                    server.starttls()
                    server.login(CREDENTIALS.smtp_username, CREDENTIALS.smtp_password)
                    server.send_message(message_text)
                external["email"] = True
                details["email"] = "DELIVERED"
                break
            except Exception as exc:
                details["email"] = f"ERROR_{type(exc).__name__}"
            if attempt < 3:
                time.sleep(2 ** attempt)
    else:
        details["email"] = "NOT_CONFIGURED"

    with db.cursor() as cur:
        for channel in ("telegram", "email"):
            cur.execute(
                """
                INSERT INTO notification_deliveries
                (event_id, channel, status, attempts, message, response_detail, acknowledged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, channel) DO UPDATE SET
                    status = excluded.status,
                    attempts = excluded.attempts,
                    message = excluded.message,
                    response_detail = excluded.response_detail,
                    attempted_at = CURRENT_TIMESTAMP,
                    acknowledged_at = excluded.acknowledged_at
                """,
                (
                    event_id,
                    channel,
                    "DELIVERED" if external[channel] else "FAILED",
                    3 if channel == "email" or channel == "telegram" else 0,
                    message,
                    details[channel],
                    time.strftime("%Y-%m-%d %H:%M:%S") if external[channel] else None,
                ),
            )

    return {
        "event_id": event_id,
        "external": external,
        "details": details,
        "verified": bool(external["telegram"] or external["email"]),
    }
