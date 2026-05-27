"""Live charts page."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from analysis.indicators import compute_indicators
from analysis.structure import support_resistance_levels
from config.settings import get_settings
from core.broker import get_broker
from dashboard.components import page_header
from data.feed import get_ohlcv


def render() -> None:
    page_header("Live Charts", "Candles, EMAs, Bollinger, RSI, MACD, S&R")
    s = get_settings()
    pairs = list(s.get("bot.pairs", ["EURUSD"]))
    timeframes = ["M5", "M15", "M30", "H1", "H4", "D1"]

    c1, c2, c3 = st.columns([2, 1, 1])
    pair = c1.selectbox("Pair", pairs, index=0)
    tf = c2.selectbox("Timeframe", timeframes,
                      index=timeframes.index(s.get("ui.default_chart_timeframe", "M15")))
    n = c3.slider("Bars", 100, 800, 300, 50)

    df = get_ohlcv(pair, tf, n=n)
    if df is None or df.empty:
        st.warning("No data — check broker connection.")
        return
    df = compute_indicators(df)
    sr = support_resistance_levels(df)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.04,
        subplot_titles=("Price", "RSI", "MACD"),
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name=pair, increasing_line_color="#00d4aa", decreasing_line_color="#ff5d6a",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], line=dict(color="#7dd3fc", width=1), name="EMA20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], line=dict(color="#fbbf24", width=1), name="EMA50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema200"], line=dict(color="#f472b6", width=1.5), name="EMA200"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], line=dict(color="rgba(255,255,255,0.25)", width=1), name="BB up", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], line=dict(color="rgba(255,255,255,0.25)", width=1), name="BB lo", showlegend=False, fill="tonexty", fillcolor="rgba(255,255,255,0.04)"), row=1, col=1)

    for lvl in sr.get("resistance", []):
        fig.add_hline(y=lvl, line=dict(color="#ff5d6a", width=1, dash="dot"), row=1, col=1)
    for lvl in sr.get("support", []):
        fig.add_hline(y=lvl, line=dict(color="#00d4aa", width=1, dash="dot"), row=1, col=1)

    # Overlay live open positions for selected pair
    broker = get_broker()
    live_positions = [p for p in broker.positions() if str(p.symbol).upper() == str(pair).upper()]
    for p in live_positions:
        side = str(p.side).upper()
        side_col = "#00d4aa" if side == "BUY" else "#ff5d6a"
        fig.add_hline(
            y=float(p.price_open),
            line=dict(color=side_col, width=2),
            row=1, col=1,
            annotation_text=f"{side} #{p.ticket} entry {p.price_open:.5f}",
            annotation_position="right",
            annotation_font_color=side_col,
        )
        if p.sl:
            fig.add_hline(
                y=float(p.sl),
                line=dict(color="#ff5d6a", width=1, dash="dash"),
                row=1, col=1,
                annotation_text=f"SL {p.sl:.5f}",
                annotation_position="right",
                annotation_font_color="#ff5d6a",
            )
        if p.tp:
            fig.add_hline(
                y=float(p.tp),
                line=dict(color="#00d4aa", width=1, dash="dash"),
                row=1, col=1,
                annotation_text=f"TP {p.tp:.5f}",
                annotation_position="right",
                annotation_font_color="#00d4aa",
            )

    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], line=dict(color="#a78bfa", width=1.5), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, line=dict(color="rgba(255,93,106,0.4)", dash="dot"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color="rgba(0,212,170,0.4)", dash="dot"), row=2, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="MACD hist",
                         marker_color=["#00d4aa" if v >= 0 else "#ff5d6a" for v in df["macd_hist"].fillna(0)]),
                  row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], line=dict(color="#7dd3fc", width=1), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], line=dict(color="#fbbf24", width=1), name="Signal"), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=560, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=6, r=6, t=30, b=6),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd2e0"),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        theme="streamlit",
        config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )
    if live_positions:
        st.caption(f"Showing {len(live_positions)} live position line(s) for {pair}.")
    elif getattr(broker, "name", "").lower() == "mock":
        st.warning("Broker mode is MOCK — chart lines reflect mock positions, not MT5 terminal orders.")

    # ---- Gemini market commentary -----------------------------------------
    st.divider()
    st.markdown("#### 🤖 AI commentary")
    cc1, cc2 = st.columns([1, 4])
    if cc1.button("💬 Explain this chart", use_container_width=True):
        last = df.iloc[-1]
        snap = {
            "symbol": pair, "timeframe": tf,
            "price": float(last["close"]),
            "ema20": float(last.get("ema20", 0)),
            "ema50": float(last.get("ema50", 0)),
            "ema200": float(last.get("ema200", 0)),
            "rsi": float(last.get("rsi", 0)),
            "atr": float(last.get("atr", 0)),
            "macd_hist": float(last.get("macd_hist", 0)),
            "bb_upper": float(last.get("bb_upper", 0)),
            "bb_lower": float(last.get("bb_lower", 0)),
            "support": sr.get("support", [])[:3],
            "resistance": sr.get("resistance", [])[:3],
        }
        with st.spinner("Asking Gemini..."):
            from ai.gemini import commentary
            text = commentary(pair, tf, snap)
        st.session_state[f"commentary_{pair}_{tf}"] = text
    text = st.session_state.get(f"commentary_{pair}_{tf}")
    if text:
        st.info(text)
    else:
        cc2.caption("Click to get a plain-English read of the current setup from Gemini.")
