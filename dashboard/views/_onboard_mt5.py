"""First-login MT5 onboarding screen."""
from __future__ import annotations

import streamlit as st

from auth.users import get_mt5_credentials, set_mt5_credentials
from journal.db import log_audit


_CSS = """
<style>
.onboard-card {
    max-width: 580px; margin: 28px auto 0;
    padding: 32px 36px;
    background: rgba(20, 26, 42, 0.70);
    backdrop-filter: blur(18px) saturate(140%);
    border: 1px solid rgba(0, 212, 170, 0.18);
    border-radius: 18px;
    box-shadow: 0 25px 60px -12px rgba(0,0,0,.55);
}
.onboard-step {
    display:inline-block; background: linear-gradient(135deg,#00d4aa,#00a085);
    color:#0a0e1a; font-weight:700; font-size:11px;
    padding: 4px 11px; border-radius: 999px; letter-spacing:.5px;
}
.onboard-h {font-size:24px; font-weight:700; color:#f1f5f9; margin: 12px 0 4px;}
.onboard-sub {color:#94a3b8; font-size:13.5px; margin: 0 0 18px;}
.onboard-tip {
    background: rgba(99,102,241,.10);
    border: 1px solid rgba(99,102,241,.25);
    color:#c7d2fe; padding: 10px 14px; border-radius: 10px;
    font-size:12.5px; margin-top:14px;
}
</style>
"""


def needs_mt5_setup(user_id: int) -> bool:
    """User must set up MT5 if no account number stored AND not skipped."""
    if st.session_state.get("mt5_setup_skipped"):
        return False
    try:
        creds = get_mt5_credentials(user_id) or {}
    except Exception:                                       # noqa: BLE001
        creds = {}
    return not creds.get("account")


def render() -> None:
    uid = st.session_state.get("auth_user_id")
    username = st.session_state.get("auth_username", "trader")

    st.markdown(_CSS, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            "<div class='onboard-card'>"
            "<span class='onboard-step'>STEP 1 OF 1</span>"
            f"<div class='onboard-h'>Welcome, {username} 👋</div>"
            "<p class='onboard-sub'>Connect your MetaTrader 5 account so AlphaBot "
            "can place trades for you. Credentials are encrypted at rest with "
            "AES-128 (Fernet) and never leave this machine.</p>",
            unsafe_allow_html=True,
        )

        with st.form("mt5_onboard_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                account = st.text_input(
                    "MT5 account number",
                    placeholder="e.g. 12345678",
                    key="onb_account",
                )
            with c2:
                server = st.text_input(
                    "Broker server",
                    placeholder="e.g. ICMarketsSC-Demo",
                    key="onb_server",
                )

            password = st.text_input(
                "MT5 password",
                type="password",
                placeholder="••••••••",
                key="onb_password",
            )

            with st.expander("Advanced (optional)"):
                path = st.text_input(
                    "Custom terminal64.exe path",
                    placeholder=r"C:\Program Files\MetaTrader 5\terminal64.exe",
                    key="onb_path",
                    help="Only set if you have multiple MT5 installs and want "
                         "AlphaBot to attach to a specific one.",
                )

            col_a, col_b = st.columns([2, 1])
            with col_a:
                submit = st.form_submit_button(
                    "🔐 Save & continue", type="primary",
                    use_container_width=True,
                )
            with col_b:
                skip = st.form_submit_button(
                    "Skip for now", use_container_width=True,
                )

        if submit:
            if not account or not password or not server:
                st.error("Account, password and server are all required.")
            elif not str(account).isdigit():
                st.error("Account number must be digits only.")
            else:
                try:
                    set_mt5_credentials(
                        uid,
                        account=str(account),
                        password=password,
                        server=server,
                        path=path or None,
                    )
                    log_audit("mt5_onboard_save", actor=username, target="self")
                    st.success("MT5 credentials saved. Loading dashboard…")
                    st.session_state.pop("mt5_setup_skipped", None)
                    st.rerun()
                except Exception as exc:                    # noqa: BLE001
                    st.error(f"Could not save: {exc}")

        if skip:
            st.session_state["mt5_setup_skipped"] = True
            log_audit("mt5_onboard_skip", actor=username)
            st.rerun()

        st.markdown(
            "<div class='onboard-tip'>💡 You can change or remove these "
            "credentials any time from <b>My Account → MT5 credentials</b>. "
            "Without them, the bot runs in <b>research-only</b> mode (signals "
            "only, no live execution).</div>"
            "</div>",
            unsafe_allow_html=True,
        )
