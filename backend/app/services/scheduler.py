from __future__ import annotations

import logging
import os
from typing import Any, Optional

from app.core.database import AsyncSessionLocal
from app.services.alert_engine import generate_alerts
from app.services.fabric_operations import generate_fabric_followup_reminders
from app.services.reminder_service import escalate_overdue_reminders
from app.services.shortage_reminders import run_daily_shortage_check


logger = logging.getLogger(__name__)


# Held as Any so this module imports cleanly even when apscheduler is not yet installed.
# The dependency is required only when start_scheduler() actually runs.
_scheduler: Optional[Any] = None


def _scheduler_enabled() -> bool:
    """Allow disabling via env (e.g., during tests or in CI)."""
    return os.getenv("DISABLE_SCHEDULER", "").lower() not in {"1", "true", "yes"} and not os.getenv("PYTEST_CURRENT_TEST")


async def _job_generate_fabric_reminders() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await generate_fabric_followup_reminders(db)
            await db.commit()
        logger.info("scheduler: generated fabric follow-up reminders")
    except Exception:
        logger.exception("scheduler: generate_fabric_followup_reminders failed")


async def _job_escalate_reminders() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await escalate_overdue_reminders(db)
        logger.info("scheduler: escalated overdue reminders")
    except Exception:
        logger.exception("scheduler: escalate_overdue_reminders failed")


async def _job_generate_alerts() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await generate_alerts(db)
            await db.commit()
        logger.info("scheduler: generated alerts")
    except Exception:
        logger.exception("scheduler: generate_alerts failed")


async def _job_check_shortages() -> None:
    """Daily — surface mill / stitching / fabric-stock shortages as reminders."""
    try:
        async with AsyncSessionLocal() as db:
            await run_daily_shortage_check(db)
            await db.commit()
        logger.info("scheduler: shortage check complete")
    except Exception:
        logger.exception("scheduler: run_daily_shortage_check failed")


def start_scheduler() -> None:
    """Start the in-process APScheduler with daily jobs.

    Jobs (UTC by default — adjust the cron expressions for the factory's timezone):
      - 03:00 daily — regenerate fabric follow-up reminders (mill delivery due/overdue/etc.)
      - 03:15 daily — escalate reminders that have been open past 24h
      - hourly — regenerate alerts so the dashboard stays fresh
    """
    global _scheduler
    if _scheduler is not None:
        return
    if not _scheduler_enabled():
        logger.info("scheduler: disabled via env")
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("scheduler: apscheduler is not installed; skipping. Run `pip install apscheduler` to enable.")
        return

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _job_generate_fabric_reminders,
        CronTrigger(hour=3, minute=0),
        id="generate_fabric_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_escalate_reminders,
        CronTrigger(hour=3, minute=15),
        id="escalate_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_generate_alerts,
        CronTrigger(minute=0),  # top of every hour
        id="generate_alerts",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_check_shortages,
        CronTrigger(hour=4, minute=0),
        id="check_shortages",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler: started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:
        logger.exception("scheduler: shutdown failed")
    finally:
        _scheduler = None
