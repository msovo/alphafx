"""Modern login & registration screen."""
from __future__ import annotations

import importlib

import streamlit as st

from auth.users import (
    authenticate,
    create_session_token,
    has_any_users,
    init_auth_db,
    register,
)
from auth.cookies import set_session_cookie


# ---------------------------------------------------------------------------
# Hardened settings switch — defensive against stale Streamlit module cache
# ---------------------------------------------------------------------------
def _switch_active_user(user_id: int) -> None:
    """Activate the user's per-user config & DB.

    Streamlit caches imported modules across reruns; if `Settings` was
    loaded before `set_active_user` existed, we force-reload to pick up
    the latest class definition.
    """
    try:
        from config import settings as _s
        if not hasattr(_s.get_settings(), "set_active_user"):
            importlib.reload(_s)
        s = _s.get_settings()
        if hasattr(s, "set_active_user"):
            s.set_active_user(user_id)
        else:
            # Last-resort fallback: poke the private attrs directly so the
            # session still works until the user restarts Streamlit.
            from auth.users import user_config_path, user_db_path
            s._user_id = user_id                            # type: ignore[attr-defined]
            s._config_file = user_config_path(user_id)     # type: ignore[attr-defined]
            s._user_db_path = user_db_path(user_id)        # type: ignore[attr-defined]
            s.reload()
    except Exception as exc:                              # noqa: BLE001
        st.warning(f"Could not switch user context cleanly: {exc}. "
                   "Please restart the app.")


def _do_login(user, *, remember: bool = False) -> None:
    st.session_state["auth_user_id"] = user.id
    st.session_state["auth_username"] = user.username
    st.session_state["auth_role"] = user.role
    _switch_active_user(user.id)
    try:
        from core.broker import reset_broker  # type: ignore
        reset_broker()
    except Exception:                                      # noqa: BLE001
        pass
    try:
        from journal.db import init_db, log_audit
        init_db()
        log_audit("login", actor=user.username,
                  meta={"remember": bool(remember)})
    except Exception:                                      # noqa: BLE001
        pass
    if remember:
        try:
            ua = st.context.headers.get("User-Agent", "")[:120] \
                if hasattr(st, "context") else ""
            tok = create_session_token(user.id, device_label=ua)
            set_session_cookie(tok)
            st.session_state["_ab_session_token"] = tok
        except Exception as exc:                           # noqa: BLE001
            st.warning(f"Could not enable auto-login: {exc}")
    st.rerun()


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
_LOGIN_CSS = """
<style>
#MainMenu, footer, header {visibility: hidden;}
section[data-testid="stSidebar"] {display: none;}

.stApp {
    background: radial-gradient(circle at 15% 20%, rgba(0,212,170,.18), transparent 45%),
                radial-gradient(circle at 85% 80%, rgba(99,102,241,.20), transparent 50%),
                linear-gradient(135deg, #0a0e1a 0%, #0f1626 50%, #0a0e1a 100%);
    background-attachment: fixed;
}

.login-card {
    max-width: 460px;
    margin: 40px auto 0;
    padding: 36px 38px 32px;
    background: rgba(20, 26, 42, 0.70);
    backdrop-filter: blur(18px) saturate(140%);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
    border: 1px solid rgba(0, 212, 170, 0.18);
    border-radius: 20px;
    box-shadow: 0 25px 60px -12px rgba(0,0,0,.55),
                0 0 0 1px rgba(255,255,255,0.02) inset;
}
.brand-wrap {text-align:center; margin: 18px 0 6px;}
.brand-logo {
    font-size: 56px; line-height: 1;
    background: linear-gradient(135deg, #00d4aa 0%, #6366f1 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 4px 16px rgba(0,212,170,.35));
    animation: pulse 3s ease-in-out infinite;
}
@keyframes pulse {
    0%,100% {filter: drop-shadow(0 4px 16px rgba(0,212,170,.35));}
    50%     {filter: drop-shadow(0 6px 22px rgba(99,102,241,.45));}
}
.brand-title {
    font-size: 30px; font-weight: 700; letter-spacing: -0.5px;
    margin: 10px 0 4px; color: #f1f5f9;
}
.brand-sub {color: #94a3b8; font-size: 13.5px; margin: 0 0 8px;}

.stTextInput > div > div > input {
    background: rgba(10, 14, 26, 0.6) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    padding: 12px 14px !important;
    transition: all .2s ease;
}
.stTextInput > div > div > input:focus {
    border-color: #00d4aa !important;
    box-shadow: 0 0 0 3px rgba(0,212,170,.15) !important;
}
.stTextInput label {color: #cbd5e1 !important; font-weight: 500 !important; font-size: 13px !important;}

.stButton > button, .stFormSubmitButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 11px 18px !important;
    transition: all .2s ease;
    border: none !important;
}
.stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00d4aa 0%, #00a085 100%) !important;
    color: #0a0e1a !important;
    box-shadow: 0 4px 14px rgba(0,212,170,.35) !important;
}
.stFormSubmitButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0,212,170,.50) !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px; background: transparent; border-bottom: 1px solid rgba(255,255,255,.06);
}
.stTabs [data-baseweb="tab"] {
    background: transparent; color: #94a3b8;
    border-radius: 8px 8px 0 0; padding: 8px 16px; font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #00d4aa !important;
    background: rgba(0,212,170,.08) !important;
}

.login-foot {
    text-align: center; color: #64748b; font-size: 11.5px;
    margin: 22px auto 0; max-width: 460px;
}
.login-foot strong {color: #94a3b8;}

.first-user {
    background: linear-gradient(135deg, rgba(99,102,241,.16), rgba(0,212,170,.10));
    border: 1px solid rgba(99,102,241,.30);
    color: #c7d2fe; padding: 10px 14px; border-radius: 10px;
    font-size: 13px; margin-bottom: 14px; text-align:center;
}

.feat-row {
    display:flex; gap:10px; justify-content:center; margin: 18px auto 0;
    max-width: 460px; flex-wrap: wrap;
}
.feat-pill {
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.06);
    color:#94a3b8; font-size:11.5px; padding:5px 11px;
    border-radius: 999px;
}
.feat-pill .dot {color:#00d4aa; margin-right:5px;}
</style>
"""


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render() -> None:
    init_auth_db()
    first_user = not has_any_users()

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            "<div class='login-card'>"
            "<div class='brand-wrap'>"
            "<div class='brand-logo'>⚡</div>"
            "<div class='brand-title'>AlphaBot FX</div>"
            "<p class='brand-sub'>Autonomous AI trading co-pilot</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if first_user:
            st.markdown(
                "<div class='first-user'>👋 First time here — "
                "create the <b>owner</b> account below.</div>",
                unsafe_allow_html=True,
            )

        tab_login, tab_register = st.tabs(
            ["🔐 Sign in", "✨ Create owner" if first_user else "✨ Register"]
        )

        # ---- Login --------------------------------------------------------
        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("Username", key="login_u",
                                  placeholder="your username")
                p = st.text_input("Password", type="password", key="login_p",
                                  placeholder="••••••••")
                remember = st.checkbox(
                    "🔒 Keep me signed in on this device (30 days)",
                    value=True, key="login_remember",
                )
                submitted = st.form_submit_button(
                    "Sign in →", type="primary", use_container_width=True
                )
            if submitted:
                if not u or not p:
                    st.error("Enter username and password.")
                else:
                    user = authenticate(u, p)
                    if user is None:
                        st.error("Invalid credentials or account inactive.")
                    else:
                        _do_login(user, remember=remember)

        # ---- Register -----------------------------------------------------
        with tab_register:
            with st.form("register_form", clear_on_submit=True):
                u = st.text_input("Choose username", key="reg_u",
                                  placeholder="trader_jane")
                e = st.text_input("Email (optional)", key="reg_e",
                                  placeholder="you@example.com")
                fn = st.text_input("Full name (optional)", key="reg_fn",
                                   placeholder="Jane Doe")
                p1 = st.text_input("Password (≥ 8 chars)", type="password",
                                   key="reg_p1", placeholder="••••••••")
                p2 = st.text_input("Confirm password", type="password",
                                   key="reg_p2", placeholder="••••••••")
                submitted = st.form_submit_button(
                    "Create owner →" if first_user else "Create account →",
                    type="primary", use_container_width=True,
                )
            if submitted:
                if p1 != p2:
                    st.error("Passwords do not match.")
                elif len(p1) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        role = "owner" if first_user else "user"
                        user = register(u, p1, email=e or None,
                                        full_name=fn or None, role=role)
                        st.success(f"Account '{user.username}' created.")
                        _do_login(user, remember=True)
                    except ValueError as ex:
                        st.error(str(ex))

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='feat-row'>"
            "<span class='feat-pill'><span class='dot'>●</span>Encrypted MT5 creds</span>"
            "<span class='feat-pill'><span class='dot'>●</span>Per-user isolated journal</span>"
            "<span class='feat-pill'><span class='dot'>●</span>Gemini 2.5 Pro</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='login-foot'>By signing in you agree this is a "
            "<strong>research tool</strong>. Trading carries risk of loss.</div>",
            unsafe_allow_html=True,
        )
