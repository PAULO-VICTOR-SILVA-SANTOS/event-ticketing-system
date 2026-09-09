from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.services.expiration_service import expire_stale_pending_participants

logger = logging.getLogger(__name__)

# One BackgroundScheduler per process, started/stopped from main.py's
# lifespan. Runs in-process (no separate worker), so on a multi-instance
# deployment each instance runs its own copy -- harmless here since
# expire_stale_pending_participants is a plain idempotent UPDATE, just
# something to know if this ever needs a second scheduled job that isn't.
scheduler = BackgroundScheduler()


def _expire_stale_pending_job() -> None:
    db = SessionLocal()
    try:
        expire_stale_pending_participants(db)
    except Exception:
        logger.exception("Falha ao rodar job de expiracao de inscricoes pendentes")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _expire_stale_pending_job,
        "interval",
        minutes=5,
        id="expire_stale_pending",
        replace_existing=True,
        next_run_time=dt.datetime.now(),
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
