"""
APScheduler-driven main loop.

Jobs:
- `signal_scan` — every N minutes (configurable), gated by session & state
- `manage_positions` — every 60 s
- `heartbeat` — every 5 min
- `account_snapshot` — every 5 min
- `daily_reset` — 00:00 UTC
- `weekly_retrain_ml` — Sunday 00:00 UTC
- `db_backup` — daily 23:55 UTC
- `weekly_report` — Sunday 22:00 UTC
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import get_settings
from core.state import get_state
from utils.logging import logger


_DOW_MAP = {
    "mon": "mon", "monday": "mon", "tue": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed", "thu": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}


def _dow(value: str) -> str:
    return _DOW_MAP.get(str(value).strip().lower(), "sun")


class AlphaScheduler:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._jobs_registered = False

    def register_jobs(self) -> None:
        if self._jobs_registered:
            return

        s = get_settings()
        scan_interval = int(s.get("bot.scan_interval_minutes", 15))

        # Lazy imports to avoid circulars
        from core.pipeline import run_signal_scan, manage_open_positions
        from journal.db import backup_database, snapshot_account
        from ml.trainer import retrain_if_due
        from journal.analytics import generate_weekly_report
        from data.session import detect_session

        def _heartbeat() -> None:
            get_state().heartbeat()
            session = detect_session()
            get_state().update(active_session=session)

        def _signal_scan() -> None:
            if not get_state().is_running:
                return
            try:
                run_signal_scan()
            except Exception as exc:                       # noqa: BLE001
                logger.exception(f"signal_scan failed: {exc}")

        def _manage_positions() -> None:
            if not get_state().is_running:
                return
            try:
                manage_open_positions()
            except Exception as exc:                       # noqa: BLE001
                logger.exception(f"manage_positions failed: {exc}")

        def _daily_reset() -> None:
            from risk.guardian import reset_daily_counters
            reset_daily_counters()

        self.scheduler.add_job(_heartbeat, IntervalTrigger(minutes=5), id="heartbeat", replace_existing=True)
        self.scheduler.add_job(_signal_scan, IntervalTrigger(minutes=scan_interval),
                               id="signal_scan", replace_existing=True, max_instances=1)
        self.scheduler.add_job(_manage_positions, IntervalTrigger(seconds=60),
                               id="manage_positions", replace_existing=True, max_instances=1)
        self.scheduler.add_job(snapshot_account, IntervalTrigger(minutes=5),
                               id="account_snapshot", replace_existing=True)
        self.scheduler.add_job(_daily_reset, CronTrigger(hour=0, minute=0),
                               id="daily_reset", replace_existing=True)
        self.scheduler.add_job(retrain_if_due,
                               CronTrigger(day_of_week=_dow(s.get("ml.retrain_day", "sun")),
                                           hour=int(s.get("ml.retrain_hour_utc", 0))),
                               id="weekly_retrain_ml", replace_existing=True)
        self.scheduler.add_job(backup_database, CronTrigger(hour=23, minute=55),
                               id="db_backup", replace_existing=True)
        self.scheduler.add_job(generate_weekly_report, CronTrigger(day_of_week="sun", hour=22, minute=0),
                               id="weekly_report", replace_existing=True)

        self._jobs_registered = True
        logger.info(f"Scheduler jobs registered (signal_scan every {scan_interval} min)")

    def start(self) -> None:
        self.register_jobs()
        if not self.scheduler.running:
            self.scheduler.start()
        logger.success("AlphaScheduler started")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("AlphaScheduler stopped")


_scheduler: AlphaScheduler | None = None


def get_scheduler() -> AlphaScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AlphaScheduler()
    return _scheduler
