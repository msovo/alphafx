"""Admin console — owner-only. Manage users + view audit log."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.users import (admin_reset_password, delete_user, get_user,
                        list_users, set_active)
from dashboard.components import page_header
from journal.db import log_audit, query


def render() -> None:
    uid = st.session_state.get("auth_user_id")
    role = st.session_state.get("auth_role", "user")
    if uid is None or role != "owner":
        st.warning("Admin console is owner-only.")
        return

    page_header("Admin", "Manage users and view the audit log")
    tabs = st.tabs(["Users", "Audit log"])

    actor = st.session_state.get("auth_username")

    # ---- Users ------------------------------------------------------------
    with tabs[0]:
        users = list_users()
        st.write(f"**{len(users)}** registered user(s)")
        for u in users:
            with st.expander(
                f"{'🛡️' if u.role == 'owner' else '👤'}  "
                f"{u.username}  ·  {u.role}  ·  "
                f"{'active' if u.active else 'suspended'}",
                expanded=False,
            ):
                c1, c2, c3 = st.columns([2, 2, 2])
                c1.write(f"**ID:** {u.id}")
                c1.write(f"**Email:** {u.email or '—'}")
                c1.write(f"**Full name:** {u.full_name or '—'}")
                c1.write(f"**Joined:** {u.created_at[:19]}")
                c1.write(f"**Last login:** {u.last_login[:19] if u.last_login else '—'}")

                with c2:
                    if u.id == uid:
                        st.caption("(this is you)")
                    else:
                        if u.active:
                            if st.button("⏸️ Suspend", key=f"suspend_{u.id}",
                                         use_container_width=True):
                                set_active(u.id, False)
                                log_audit("user_suspend", actor=actor, target=u.username)
                                st.rerun()
                        else:
                            if st.button("▶️ Activate", key=f"activate_{u.id}",
                                         use_container_width=True):
                                set_active(u.id, True)
                                log_audit("user_activate", actor=actor, target=u.username)
                                st.rerun()

                with c3:
                    if u.id != uid:
                        with st.popover("🔑 Reset password", use_container_width=True):
                            new_pwd = st.text_input(
                                "New password (≥ 8)", type="password",
                                key=f"resetpwd_{u.id}")
                            if st.button("Reset", key=f"do_reset_{u.id}",
                                         type="primary"):
                                try:
                                    admin_reset_password(u.id, new_pwd)
                                    log_audit("user_reset_password",
                                              actor=actor, target=u.username)
                                    st.success("Password reset.")
                                except ValueError as e:
                                    st.error(str(e))

                        with st.popover("🗑️ Delete", use_container_width=True):
                            st.warning(f"Delete user **{u.username}**?")
                            wipe = st.checkbox("Also wipe their trade data + config",
                                               key=f"wipe_{u.id}")
                            if st.button("Confirm delete", key=f"do_del_{u.id}",
                                         type="primary"):
                                delete_user(u.id, wipe_data=wipe)
                                log_audit("user_delete", actor=actor,
                                          target=u.username,
                                          meta={"wipe_data": wipe})
                                st.rerun()

    # ---- Audit log --------------------------------------------------------
    with tabs[1]:
        df = query(
            "SELECT timestamp, actor, action, target, meta "
            "FROM audit_log ORDER BY id DESC LIMIT 500"
        )
        if df.empty:
            st.info("Audit log is empty.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export CSV", df.to_csv(index=False).encode("utf-8"),
                file_name="alphabot_audit_log.csv", mime="text/csv",
            )
