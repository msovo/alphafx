"""Cookie helper for persistent device sessions.

Uses `extra-streamlit-components.CookieManager` to read/write a single
`alphabot_session` cookie on the browser. Falls back gracefully if the
package is unavailable (just disables remember-me).
"""
from __future__ import annotations

import streamlit as st

COOKIE_NAME = "alphabot_session"
COOKIE_MAX_AGE_DAYS = 30


def _manager():
    """Create or reuse a single CookieManager per session.

    extra-streamlit-components requires a singleton with a fixed `key`,
    or it loops infinitely on rerun.
    """
    try:
        import extra_streamlit_components as stx
    except Exception:                                       # noqa: BLE001
        return None
    if "_ab_cookie_mgr" not in st.session_state:
        st.session_state["_ab_cookie_mgr"] = stx.CookieManager(key="ab_cookies")
    return st.session_state["_ab_cookie_mgr"]


def get_session_cookie() -> str | None:
    cm = _manager()
    if cm is None:
        return None
    try:
        return cm.get(COOKIE_NAME)
    except Exception:                                       # noqa: BLE001
        return None


def set_session_cookie(token: str) -> None:
    cm = _manager()
    if cm is None:
        return
    import datetime as dt
    try:
        cm.set(
            COOKIE_NAME,
            token,
            expires_at=dt.datetime.utcnow() + dt.timedelta(days=COOKIE_MAX_AGE_DAYS),
            key=f"ab_set_{token[:8]}",
        )
    except Exception:                                       # noqa: BLE001
        pass


def clear_session_cookie() -> None:
    cm = _manager()
    if cm is None:
        return
    try:
        cm.delete(COOKIE_NAME, key="ab_clr")
    except Exception:                                       # noqa: BLE001
        pass
