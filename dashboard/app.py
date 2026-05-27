"""
AlphaBot FX — Streamlit dashboard entry point.

Run: `streamlit run dashboard/app.py`

Streamlit auto-discovers files in `pages/`, but we also expose a
sidebar-driven navigation via `streamlit-option-menu` for a nicer mobile UX.
"""
from __future__ import annotations

# Make repo root importable regardless of CWD when launched by Streamlit
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config.settings import get_settings
from core.state import get_state
from dashboard.components import inject_css, page_header
from journal.db import init_db
from utils.logging import logger


def _bootstrap() -> None:
    if "_bootstrapped" not in st.session_state:
        from auth.users import init_auth_db
        init_auth_db()
        st.session_state["_bootstrapped"] = True
        logger.info("Dashboard bootstrapped")
    # If user logged in, ensure settings target their config & init their DB
    uid = st.session_state.get("auth_user_id")
    if uid is not None:
        s = get_settings()
        if s.active_user_id != uid:
            s.set_active_user(uid)
        init_db()
    get_state()


# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AlphaBot FX",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
_bootstrap()

# ---------------------------------------------------------------------------
# Auth gate — show login screen if not signed in
# ---------------------------------------------------------------------------
if "auth_user_id" not in st.session_state:
    from dashboard.views import _login
    _login.render()
    st.stop()


# ---------------------------------------------------------------------------
# First-login MT5 onboarding gate
# ---------------------------------------------------------------------------
from dashboard.views import _onboard_mt5
if _onboard_mt5.needs_mt5_setup(st.session_state["auth_user_id"]):
    _onboard_mt5.render()
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar navigation (signed in)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚡ AlphaBot FX")
    st.caption(f"Signed in as **{st.session_state.get('auth_username','?')}**")

    is_owner = st.session_state.get("auth_role") == "owner"
    nav_options = ["Overview", "Live Charts", "Signals", "Trade Journal",
                   "Calendar", "AI Insights", "Risk Monitor",
                   "Settings", "My Account", "Backtester"]
    nav_icons = ["speedometer2", "graph-up", "broadcast", "journal-text",
                 "calendar3", "cpu", "shield-check",
                 "gear", "person-circle", "rewind"]
    if is_owner:
        nav_options.append("Admin")
        nav_icons.append("shield-lock")

    try:
        from streamlit_option_menu import option_menu
        choice = option_menu(
            menu_title=None,
            options=nav_options,
            icons=nav_icons,
            default_index=0,
            styles={
                "container": {"background-color": "transparent", "padding": "0"},
                "icon": {"color": "#00d4aa", "font-size": "16px"},
                "nav-link": {"font-size": "14px", "color": "#cbd2e0", "border-radius": "8px"},
                "nav-link-selected": {"background-color": "rgba(0,212,170,0.13)", "color": "#00d4aa", "font-weight": "600"},
            },
        )
    except Exception:                                      # noqa: BLE001
        choice = st.radio("Navigate", nav_options)

    st.markdown("---")
    state = get_state().state
    pill_kind = {"running": "good", "paused": "warn", "stopped": "", "kill_switch": "bad"}.get(state.status, "")
    st.markdown(
        f"<div style='padding:6px 0'><span class='ab-pill {pill_kind}'>{state.status.upper()}</span> "
        f"<span class='ab-pill'>{state.mode}</span></div>",
        unsafe_allow_html=True,
    )
    # Show heartbeat in SAST (South African time)
    hb = state.last_heartbeat
    if hb:
        try:
            from datetime import datetime
            from utils.helpers import to_sast
            dt = datetime.fromisoformat(hb.replace(" ", "T"))
            hb = to_sast(dt).strftime("%H:%M:%S SAST")
        except Exception:                                  # noqa: BLE001
            pass
    st.caption(f"Heartbeat: {hb or '—'}")

    st.markdown("---")
    # Broker status pill
    from core.broker import get_broker as _get_broker, HAS_MT5
    _broker = _get_broker()
    if _broker.name == "mock":
        st.markdown(
            "<div style='background:rgba(255,170,0,0.15);border:1px solid #ffaa00;"
            "border-radius:8px;padding:8px 12px;font-size:0.82em;color:#ffcc55;"
            "margin-bottom:8px'>⚠️ <b>MockBroker</b> — yfinance data<br>"
            "<span style='color:#94a3b8'>MT5 terminal not connected.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        _ai = _broker.account_info()
        _label = f"{_ai.login} @ {_ai.server}" if _ai else "MT5 connected"
        st.markdown(
            f"<div style='background:rgba(0,212,170,0.1);border:1px solid #00d4aa;"
            f"border-radius:8px;padding:8px 12px;font-size:0.82em;color:#00d4aa;"
            f"margin-bottom:8px'>✅ <b>MT5 Live</b><br>"
            f"<span style='color:#94a3b8'>{_label}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if st.button("🚪 Sign out", use_container_width=True):
        # Audit + stop bot if running
        try:
            from journal.db import log_audit
            log_audit("logout", actor=st.session_state.get("auth_username"))
        except Exception:                                  # noqa: BLE001
            pass
        try:
            from core.scheduler import get_scheduler
            get_state().stop()
            get_scheduler().shutdown()
        except Exception:                                  # noqa: BLE001
            pass
        for k in ("auth_user_id", "auth_username", "auth_role", "_bootstrapped"):
            st.session_state.pop(k, None)
        get_settings().set_active_user(None)
        try:
            from core.broker import reset_broker  # type: ignore
            reset_broker()
        except Exception:                                  # noqa: BLE001
            pass
        st.rerun()


# ---------------------------------------------------------------------------
# Global MockBroker warning banner (shown on every page)
# ---------------------------------------------------------------------------
from core.broker import get_broker as _gb, HAS_MT5 as _HAS_MT5
_active_broker = _gb()
if _active_broker.name == "mock":
    st.warning(
        "**MockBroker active** — all prices, charts and signals are sourced from "
        "**yfinance** (delayed/synthetic), NOT from your MT5 account.\n\n"
        "**To connect real MT5 data:** start the MetaTrader 5 terminal, then set "
        "your credentials in **My Account → MT5 credentials** and restart the app.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Page dispatch
# ---------------------------------------------------------------------------
PAGES = {
    "Overview":      "dashboard.views._overview",
    "Live Charts":   "dashboard.views._charts",
    "Signals":       "dashboard.views._signals",
    "Trade Journal": "dashboard.views._journal",
    "Calendar":      "dashboard.views._calendar",
    "AI Insights":   "dashboard.views._ai",
    "Risk Monitor":  "dashboard.views._risk",
    "Settings":      "dashboard.views._settings",
    "My Account":    "dashboard.views._account",
    "Backtester":    "dashboard.views._backtester",
    "Admin":         "dashboard.views._admin",
}

import importlib
mod = importlib.import_module(PAGES[choice])
if hasattr(mod, "render"):
    mod.render()
else:
    page_header("AlphaBot FX", "Module missing render()")
