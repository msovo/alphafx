"""
AlphaBot FX — autonomous scheduler entry point.

Runs the bot loop without the dashboard. Use this on a VPS or alongside
`streamlit run dashboard/app.py` on your local machine.

    python main.py            # blocks; Ctrl-C to stop
"""
from __future__ import annotations

import signal
import sys
import time

from config.settings import get_settings
from core.broker import get_broker
from core.scheduler import get_scheduler
from core.state import get_state
from journal.db import init_db
from utils.logging import logger


def main() -> int:
    s = get_settings()
    logger.info(f"AlphaBot FX starting — env={s.app_env}")
    init_db()
    broker = get_broker()
    if not broker.connected:
        logger.error("Broker connection failed; aborting")
        return 1

    scheduler = get_scheduler()
    scheduler.start()
    state = get_state()
    state.start()
    logger.success(f"AlphaBot FX running ({state.state.mode}). Ctrl-C to stop.")

    def _shutdown(signum, frame):                          # noqa: ANN001, ARG001
        logger.info("Shutdown signal received")
        state.stop()
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        _shutdown(0, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
