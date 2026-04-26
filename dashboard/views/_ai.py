"""AI Insights page."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components import page_header
from journal.db import query
from ml.model import feature_importance, latest_metrics, train_model


def render() -> None:
    page_header("AI Insights", "ML performance + Gemini decision log")

    metrics = latest_metrics() or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accuracy", f"{(metrics.get('accuracy') or 0)*100:.1f}%")
    c2.metric("Precision", f"{(metrics.get('precision') or 0)*100:.1f}%")
    c3.metric("Recall", f"{(metrics.get('recall') or 0)*100:.1f}%")
    c4.metric("F1", f"{(metrics.get('f1') or 0)*100:.1f}%")

    if st.button("🌲 Retrain ML model now"):
        with st.spinner("Training Random Forest..."):
            res = train_model()
        if res:
            st.success(f"Trained: {res['metrics']}")
        else:
            st.warning("Not enough labelled trades yet (need ≥ 100 closed trades).")

    fi = feature_importance()
    if fi:
        df_fi = pd.DataFrame({"feature": list(fi), "importance": list(fi.values())}).sort_values("importance", ascending=True)
        fig = px.bar(df_fi, x="importance", y="feature", orientation="h",
                     title="Feature importance", template="plotly_dark",
                     color_discrete_sequence=["#00d4aa"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=40, b=10), height=420)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("#### Gemini decision log")
    df = query("SELECT id, timestamp, signal_id, model, latency_ms, error, response FROM ai_log ORDER BY id DESC LIMIT 100")
    if df.empty:
        st.info("No AI calls yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
