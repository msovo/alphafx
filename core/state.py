"""
Global bot state — shared between scheduler, dashboard, and modules.

Thread-safe singleton; persists snapshot to disk so the dashboard
process can read the same state.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from config.settings import DATA_DIR
from utils.helpers import utcnow_iso

STATE_FILE: Path = DATA_DIR / "state.json"

BotMode = Literal["signal_only", "manual_confirm", "full_auto"]
BotStatus = Literal["stopped", "running", "paused", "kill_switch"]


@dataclass
class BotState:
    status: BotStatus = "stopped"
    mode: BotMode = "signal_only"
    started_at: str | None = None
    last_heartbeat: str | None = None
    last_scan: str | None = None
    last_error: str | None = None
    open_positions: int = 0
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_dd_pct: float = 0.0
    total_dd_pct: float = 0.0
    peak_equity: float = 0.0
    kill_switch_reason: str | None = None
    active_session: str | None = None
    next_news_event: str | None = None
    notes: list[str] = field(default_factory=list)


class StateStore:
    _instance: "StateStore | None" = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self._state = BotState()
        self.load()

    # -- persistence -------------------------------------------------------

    def load(self) -> None:
        if STATE_FILE.exists():
            try:
                raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                self._state = BotState(**{**asdict(BotState()), **raw})
            except Exception:                              # noqa: BLE001
                self._state = BotState()

    def save(self) -> None:
        with self._lock:
            STATE_FILE.write_text(json.dumps(asdict(self._state), indent=2), encoding="utf-8")

    # -- mutators ----------------------------------------------------------

    def update(self, **kwargs: object) -> BotState:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state, k):
                    setattr(self._state, k, v)
            self.save()
            return self._state

    def heartbeat(self) -> None:
        self.update(last_heartbeat=utcnow_iso())

    def start(self, mode: BotMode | None = None) -> None:
        self.update(status="running", started_at=utcnow_iso(), kill_switch_reason=None,
                    mode=mode or self._state.mode)

    def stop(self) -> None:
        self.update(status="stopped")

    def pause(self) -> None:
        self.update(status="paused")

    def resume(self) -> None:
        self.update(status="running")

    def trigger_kill_switch(self, reason: str) -> None:
        self.update(status="kill_switch", kill_switch_reason=reason)

    # -- accessors ---------------------------------------------------------

    @property
    def state(self) -> BotState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state.status == "running"

    @property
    def is_killed(self) -> bool:
        return self._state.status == "kill_switch"


def get_state() -> StateStore:
    if StateStore._instance is None:
        with StateStore._lock:
            if StateStore._instance is None:
                StateStore._instance = StateStore()
    return StateStore._instance
