"""Twilio SMS sending, with a dry-run mode that prints instead of sending."""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)


def _safe_print(text: str) -> None:
    """Print, tolerating consoles (e.g. Windows cp1252) that can't encode emoji."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    sys.stdout.write(text.encode(enc, errors="replace").decode(enc) + "\n")


def _client():
    from twilio.rest import Client

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    return Client(sid, token)


def send_sms(to: str, body: str, *, from_number: str, dry_run: bool = False) -> None:
    """Send a single SMS. In dry-run mode, print the message instead."""
    if dry_run:
        _safe_print(f"\n--- SMS to {to} ({len(body)} chars) ---\n{body}")
        return
    message = _client().messages.create(to=to, from_=from_number, body=body)
    log.info("Sent SMS to %s (sid=%s)", to, message.sid)


def broadcast(
    recipients: list[str],
    bodies: list[str],
    *,
    from_number: str | None,
    dry_run: bool = False,
) -> int:
    """Send every body to every recipient. Returns the count of messages sent."""
    if not bodies:
        log.info("Nothing to send.")
        return 0
    if not dry_run and not from_number:
        raise RuntimeError("TWILIO_FROM_NUMBER is not set; cannot send live SMS.")

    count = 0
    for to in recipients:
        for body in bodies:
            send_sms(to, body, from_number=from_number or "", dry_run=dry_run)
            count += 1
    log.info("%s %d message(s) across %d recipient(s)",
             "Would send" if dry_run else "Sent", count, len(recipients))
    return count
