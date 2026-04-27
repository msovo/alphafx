"""Cookie helper for persistent device sessions.

Uses `extra-streamlit-components.CookieManager` to read/write a single
`alphabot_session` cookie on the browser.

IMPORTANT: The CookieManager is a JS component — it must be **rendered**
(mounted) on the page before reads/writes commit to the browser. We mount
a single instance at the top of `app.py` via `mount()`. After `set()`
or `delete()`, the *next* Streamlit run will see the new cookie value.
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st

COOKIE_NAME = "alphabot_session"
COOKIE_MAX_AGE_DAYS = 30
_MGR_KEY = "_ab_cookie_mgr"


def mount() -> None:
    """Create + mount the cookie manager once per session.

    Must be called early on every page load (before any read/write).
    """
    try:
        import extra_streamlit_components as stx
    except Exception:                                       # noqa: BLE001
        return
    if _MGR_KEY not in st.session_state:
        st.session_state[_MGR_KEY] = stx.CookieManager(key="ab_cookies")
    # Calling get_all() forces the component to render so subsequent
    # set/delete actually take effect on the next rerun.
    try:
        st.session_state[_MGR_KEY].get_all(key="ab_cookies_all")
    except Exception:                                       # noqa: BLE001
        pass


def _mgr():
    return st.session_state.get(_MGR_KEY)


def get_session_cookie() -> str | None:
    cm = _mgr()
    if cm is None:
        return None
    try:
        return cm.get(COOKIE_NAME)
    except Exception:                                       # noqa: BLE001
        return None


def set_session_cookie(token: str) -> None:
    cm = _mgr()
    if cm is None:
        return
    try:
        cm.set(
            COOKIE_NAME,
            token,
            expires_at=_dt.datetime.utcnow() + _dt.timedelta(days=COOKIE_MAX_AGE_DAYS),
            key=f"ab_set_{token[:8]}",
        )
    except Exception:                                       # noqa: BLE001
        pass


def clear_session_cookie() -> None:
    cm = _mgr()
    if cm is None:
        return
    try:
        cm.delete(COOKIE_NAME, key="ab_clr_cookie")
    except Exception:                                       # noqa: BLE001
        pass
