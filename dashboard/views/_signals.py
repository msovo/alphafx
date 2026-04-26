"""Signals page."""
from __future__ import annotations

import json

import streamlit as st

from dashboard.components import page_header
from journal.db import query


def render() -> None:
    page_header("Signals", "Pipeline activity — last 100 candidates")

    df = query("SELECT * FROM signals ORDER BY id DESC LIMIT 100")
    if df.empty:
        st.info("No signals yet.")
        return

    cols = st.columns(4)
    pair = cols[0].selectbox("Pair", ["All"] + sorted(df["pair"].dropna().unique().tolist()))
    stage = cols[1].selectbox("Filter stage", ["All"] + sorted(df["filter_stage"].dropna().unique().tolist()))
    decision = cols[2].selectbox("AI decision", ["All"] + sorted(df["ai_decision"].dropna().unique().tolist()))
    executed = cols[3].selectbox("Executed", ["All", "Yes", "No"])

    f = df.copy()
    if pair != "All":      f = f[f["pair"] == pair]
    if stage != "All":     f = f[f["filter_stage"] == stage]
    if decision != "All":  f = f[f["ai_decision"] == decision]
    if executed != "All":  f = f[f["executed"] == (1 if executed == "Yes" else 0)]

    st.markdown(f"**{len(f)}** signals match")
    show_cols = ["timestamp", "pair", "direction", "confluence_score",
                 "ml_probability", "ai_decision", "ai_confidence",
                 "rr", "filter_stage", "executed"]
    st.dataframe(f[show_cols], use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Inspect signal")
    sig_id = st.number_input("Signal ID", min_value=int(f["id"].min()) if not f.empty else 0,
                             max_value=int(f["id"].max()) if not f.empty else 0,
                             value=int(f["id"].iloc[0]) if not f.empty else 0, step=1)
    if sig_id:
        row = df[df["id"] == sig_id]
        if not row.empty:
            r = row.iloc[0].to_dict()
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Setup**")
                st.json({k: r.get(k) for k in ["pair", "direction", "entry", "sl", "tp", "rr", "session"]})
                st.write("**AI**")
                st.json({"decision": r.get("ai_decision"), "confidence": r.get("ai_confidence"),
                         "reason": r.get("ai_reason"), "risk_flag": r.get("ai_risk_flag")})
            with c2:
                st.write("**Indicators**")
                try:
                    st.json(json.loads(r.get("indicator_snapshot") or "{}"))
                except Exception:
                    st.code(r.get("indicator_snapshot"))
                st.write("**MTF / Patterns / Structure**")
                try:
                    st.json(json.loads(r.get("meta") or "{}"))
                except Exception:
                    st.code(r.get("meta"))
