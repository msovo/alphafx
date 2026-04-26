"""Auto-retraining job — invoked weekly by the scheduler."""
from __future__ import annotations

from journal.db import query
from ml.model import train_model
from utils.logging import logger


def retrain_if_due() -> None:
    df = query("SELECT COUNT(*) as n FROM trades WHERE status='closed'")
    n = int(df["n"].iloc[0]) if not df.empty else 0
    last = query("SELECT n_samples FROM ml_runs ORDER BY id DESC LIMIT 1")
    last_n = int(last["n_samples"].iloc[0]) if not last.empty else 0
    if n - last_n < 50 and last_n > 0:
        logger.info(f"Retrain skipped (only {n - last_n} new trades since last run)")
        return
    train_model()
