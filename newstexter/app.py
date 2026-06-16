"""Always-on FastAPI service: inbound /sms webhook + scheduled digest jobs."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request, Response

from .config import load_config
from .format import chunk
from .main import run_cycle
from .reply import answer
from . import store

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

config = load_config()
scheduler = BackgroundScheduler()


def _normalize(number: str) -> str:
    return number.strip().replace(" ", "").replace("-", "")


ALLOWLIST = {_normalize(n) for n in config.recipients}


def _schedule_jobs() -> None:
    minutes = config.settings.poll_interval_minutes
    scheduler.add_job(
        lambda: run_cycle(config),
        IntervalTrigger(minutes=minutes),
        id="poll",
        replace_existing=True,
        max_instances=1,          # don't overlap if a cycle runs long
        coalesce=True,            # collapse missed runs into one
    )
    log.info("Scheduled story poll every %d min", minutes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _schedule_jobs()
    scheduler.start()
    log.info("NewsTexter service started.")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="NewsTexter", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "recipients": len(ALLOWLIST)}


def _twiml(messages: list[str]) -> Response:
    """Build a TwiML response with one <Message> element per chunk."""
    from xml.sax.saxutils import escape

    body = "".join(f"<Message>{escape(m)}</Message>" for m in messages)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(content=xml, media_type="application/xml")


def _valid_signature(request: Request, form: dict) -> bool:
    if config.skip_twilio_validation:
        return True
    from twilio.request_validator import RequestValidator

    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not token:
        log.error("TWILIO_AUTH_TOKEN unset; rejecting inbound request.")
        return False
    validator = RequestValidator(token)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(str(request.url), form, signature)


@app.post("/sms")
async def sms(request: Request):
    form = dict(await request.form())

    if not _valid_signature(request, form):
        log.warning("Rejected inbound /sms: bad Twilio signature.")
        return Response(status_code=403)

    from_number = _normalize(form.get("From", ""))
    body = (form.get("Body") or "").strip()

    # Abuse/cost guard: only answer known recipients.
    if from_number not in ALLOWLIST:
        log.warning("Ignoring inbound from non-allowlisted number %s", from_number)
        return _twiml([])
    if not body:
        return _twiml([])

    with store.connect(config.db_path) as conn:
        history = store.get_history(conn, from_number, limit=6)
        reply = answer(body, config.settings, history=history)
        store.add_message(conn, from_number, "user", body)
        store.add_message(conn, from_number, "assistant", reply)

    return _twiml(chunk(reply))
