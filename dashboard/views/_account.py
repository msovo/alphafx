"""My Account — change password, manage MT5 credentials."""
from __future__ import annotations

import streamlit as st

from auth.users import (change_password, get_mt5_credentials, get_user,
                        set_mt5_credentials)
from dashboard.components import page_header


def render() -> None:
    uid = st.session_state.get("auth_user_id")
    if uid is None:
        st.warning("Not signed in.")
        return
    user = get_user(uid)
    page_header(f"My Account — {user.username}",
                f"Role: {user.role}  •  Joined {user.created_at[:10]}")

    tabs = st.tabs(["MT5 credentials", "Change password", "Profile"])

    # ---- MT5 ---------------------------------------------------------------
    with tabs[0]:
        st.markdown("Your MT5 login is **encrypted at rest** with AES-128 (Fernet). "
                    "Only this app can read it back.")
        creds = get_mt5_credentials(uid)
        with st.form("mt5_form"):
            acc = st.text_input("MT5 account number",
                                value=creds.get("account") or "")
            pwd = st.text_input("MT5 password (leave blank to keep current)",
                                type="password")
            srv = st.text_input("MT5 server", value=creds.get("server") or "")
            pth = st.text_input("MT5 terminal path (optional)",
                                value=creds.get("path") or "",
                                help=r"e.g. C:\Program Files\MetaTrader 5\terminal64.exe")
            saved = st.form_submit_button("💾 Save MT5 credentials",
                                          type="primary", use_container_width=True)
        if saved:
            new_pwd = pwd if pwd else creds.get("password")
            set_mt5_credentials(
                uid,
                account=acc.strip() or None,
                password=new_pwd,
                server=srv.strip() or None,
                path=pth.strip() or None,
            )
            try:
                from core.broker import reset_broker  # type: ignore
                reset_broker()
            except Exception:                              # noqa: BLE001
                pass
            st.success("MT5 credentials saved. Restart the bot to reconnect.")

    # ---- Password ----------------------------------------------------------
    with tabs[1]:
        with st.form("pwd_form", clear_on_submit=True):
            old = st.text_input("Current password", type="password")
            new1 = st.text_input("New password", type="password")
            new2 = st.text_input("Confirm new password", type="password")
            ok = st.form_submit_button("Change password", type="primary",
                                       use_container_width=True)
        if ok:
            if new1 != new2:
                st.error("New passwords don't match.")
            elif len(new1) < 8:
                st.error("Password must be at least 8 characters.")
            elif not change_password(uid, old, new1):
                st.error("Current password is wrong.")
            else:
                st.success("Password changed.")

    # ---- Profile -----------------------------------------------------------
    with tabs[2]:
        st.write(f"**Username:** `{user.username}`")
        st.write(f"**Email:** {user.email or '—'}")
        st.write(f"**Full name:** {user.full_name or '—'}")
        st.write(f"**Role:** {user.role}")
        st.write(f"**Last login:** {user.last_login or '—'}")
        st.divider()
        st.caption("Each user has an **isolated** trade journal, settings, "
                   "and runtime state — kept under `data/users/<id>/`.")
