"""Settings page — full UI-driven bot configuration."""
from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from core.state import get_state
from dashboard.components import page_header

PROP_PROFILES = {
    "fundednext_stellar": {"daily_loss_limit_pct": 5.0, "max_drawdown_pct": 10.0},
    "ftmo":               {"daily_loss_limit_pct": 5.0, "max_drawdown_pct": 10.0},
    "myforexfunds":       {"daily_loss_limit_pct": 5.0, "max_drawdown_pct": 12.0},
    "custom":             {"daily_loss_limit_pct": 5.0, "max_drawdown_pct": 10.0},
}


def _section(title: str) -> None:
    st.markdown(f"### {title}")


def render() -> None:
    page_header("Settings", "Configure the bot live — all changes saved to config.json")
    s = get_settings()
    cfg = s.data

    tabs = st.tabs(["Bot", "Strategy", "User Targets", "Risk", "Prop Firm",
                    "AI", "Validators", "Localization",
                    "ML", "News", "Notifications", "Instruments"])

    # ---- Bot tab -----------------------------------------------------------
    with tabs[0]:
        _section("Bot")
        col1, col2 = st.columns(2)
        with col1:
            mode = st.selectbox("Mode", ["signal_only", "manual_confirm", "full_auto"],
                                index=["signal_only", "manual_confirm", "full_auto"].index(cfg["bot"]["mode"]))
            scan = st.number_input("Scan interval (min)", 1, 240, int(cfg["bot"]["scan_interval_minutes"]))
            primary = st.selectbox("Primary timeframe", ["M5","M15","M30","H1","H4"],
                                   index=["M5","M15","M30","H1","H4"].index(cfg["bot"].get("primary_timeframe","M15")))
        with col2:
            sessions = st.multiselect("Active sessions",
                                      ["asia","london","new_york","overlap"],
                                      default=cfg["bot"]["active_sessions"])
            pairs = st.multiselect("Pairs", list(cfg.get("instruments", {}).keys()),
                                   default=cfg["bot"]["pairs"])
            trend_tf = st.selectbox("Trend timeframe", ["H1","H4","D1"],
                                    index=["H1","H4","D1"].index(cfg["bot"].get("trend_timeframe","H4")))

    # ---- Strategy tab ------------------------------------------------------
    with tabs[1]:
        _section("Strategy")
        col1, col2 = st.columns(2)
        with col1:
            strat_name = st.text_input("Strategy name", cfg["strategy"]["name"])
            min_conf = st.slider("Min confluence score", 0, 100, int(cfg["strategy"]["min_confluence_score"]))
            min_rr = st.number_input("Min R:R", 0.5, 10.0, float(cfg["strategy"]["min_rr"]), 0.1)
            target_rr = st.number_input("Target R:R", 0.5, 10.0, float(cfg["strategy"]["target_rr"]), 0.1)
        with col2:
            require_mtf = st.checkbox("Require MTF alignment", bool(cfg["strategy"]["require_mtf_alignment"]))
            use_pat = st.checkbox("Use pattern filter", bool(cfg["strategy"]["use_pattern_filter"]))
            use_sess = st.checkbox("Use session filter", bool(cfg["strategy"]["use_session_filter"]))
        st.text_area("Custom rules (free-form notes — passed to the AI)",
                     "\n".join(cfg["strategy"].get("custom_rules", [])), key="strategy_rules", height=120)

    # ---- User Targets ------------------------------------------------------
    with tabs[2]:
        _section("Profit / time targets")
        col1, col2 = st.columns(2)
        with col1:
            profit_target = st.number_input("Profit target (%)", 0.0, 200.0, float(cfg["user_targets"]["profit_target_pct"]), 0.5, key="ut_profit_target")
            max_days = st.number_input("Max days to target", 1, 365, int(cfg["user_targets"]["max_days_to_target"]), key="ut_max_days")
            max_per_day = st.number_input("Max trades per day", 1, 50, int(cfg["user_targets"]["max_trades_per_day"]), key="ut_max_per_day")
        with col2:
            preferred_pairs = st.multiselect("Preferred pairs", list(cfg.get("instruments", {}).keys()),
                                             default=cfg["user_targets"]["preferred_pairs"], key="ut_pairs")
            preferred_sessions = st.multiselect("Preferred sessions", ["asia","london","new_york","overlap"],
                                                default=cfg["user_targets"]["preferred_sessions"], key="ut_sessions")

    # ---- Risk --------------------------------------------------------------
    with tabs[3]:
        _section("Risk")
        col1, col2, col3 = st.columns(3)
        with col1:
            risk_pct = st.number_input("Risk % per trade", 0.05, 5.0, float(cfg["risk"]["risk_pct_per_trade"]), 0.05, key="rk_risk_pct")
            max_conc = st.number_input("Max concurrent", 1, 20, int(cfg["risk"]["max_concurrent_trades"]), key="rk_max_conc")
            max_daily = st.number_input("Max daily trades", 1, 50, int(cfg["risk"]["max_daily_trades"]), key="rk_max_daily")
            max_spread = st.number_input("Max spread (pips)", 0.0, 50.0, float(cfg["risk"]["max_spread_pips"]), 0.1, key="rk_max_spread")
        with col2:
            daily_loss = st.number_input("Daily loss limit %", 0.5, 50.0, float(cfg["risk"]["daily_loss_limit_pct"]), 0.1, key="rk_daily_loss")
            max_dd = st.number_input("Max drawdown %", 1.0, 50.0, float(cfg["risk"]["max_drawdown_pct"]), 0.1, key="rk_max_dd")
            warn_pct = st.number_input("Kill-switch warn %", 50, 99, int(cfg["risk"]["kill_switch_warning_pct"]), key="rk_warn")
        with col3:
            atr_sl = st.number_input("ATR SL multiplier", 0.5, 5.0, float(cfg["risk"]["atr_sl_multiplier"]), 0.1, key="rk_atr_sl")
            atr_tp = st.number_input("ATR TP multiplier", 0.5, 10.0, float(cfg["risk"]["atr_tp_multiplier"]), 0.1, key="rk_atr_tp")
            be_r = st.number_input("Breakeven at R", 0.0, 5.0, float(cfg["risk"]["breakeven_at_r"]), 0.1, key="rk_be_r")
            partial_r = st.number_input("Partial close at R", 0.0, 10.0, float(cfg["risk"]["partial_close_at_r"]), 0.1, key="rk_partial_r")
            partial_pct = st.number_input("Partial close %", 0, 100, int(cfg["risk"]["partial_close_pct"]), key="rk_partial_pct")

    # ---- Prop firm ---------------------------------------------------------
    with tabs[4]:
        _section("Prop firm")
        profile = st.selectbox("Profile", list(PROP_PROFILES.keys()),
                               index=list(PROP_PROFILES.keys()).index(cfg["prop_firm"]["profile"]), key="pf_profile")
        defaults = PROP_PROFILES[profile]
        pf_daily = st.number_input("Daily loss limit %", 0.5, 50.0,
                                   float(cfg["prop_firm"].get("daily_loss_limit_pct", defaults["daily_loss_limit_pct"])), 0.1, key="pf_daily")
        pf_dd = st.number_input("Max drawdown %", 1.0, 50.0,
                                float(cfg["prop_firm"].get("max_drawdown_pct", defaults["max_drawdown_pct"])), 0.1, key="pf_dd")
        pf_news_b = st.number_input("News block before (min)", 0, 240, int(cfg["prop_firm"]["news_block_before_min"]), key="pf_news_b")
        pf_news_a = st.number_input("News block after (min)", 0, 240, int(cfg["prop_firm"]["news_block_after_min"]), key="pf_news_a")

    # ---- AI ----------------------------------------------------------------
    with tabs[5]:
        _section("AI Reasoning (Gemini)")
        ai_backend = st.selectbox(
            "Backend",
            ["studio", "vertex"],
            index=["studio", "vertex"].index(cfg["ai"].get("backend", "studio")),
            key="ai_backend",
            help="studio = Google AI Studio (API key). vertex = Google Cloud Vertex AI (works with free GCP credit)."
        )
        if ai_backend == "vertex":
            vc1, vc2 = st.columns(2)
            vertex_project = vc1.text_input("GCP project ID", cfg["ai"].get("vertex_project", ""), key="vertex_project")
            vertex_location = vc2.text_input("Location", cfg["ai"].get("vertex_location", "us-central1"), key="vertex_location")
            st.caption("Run `gcloud auth application-default login` once on this machine before starting the bot.")
        else:
            vertex_project = cfg["ai"].get("vertex_project", "")
            vertex_location = cfg["ai"].get("vertex_location", "us-central1")
            st.caption("Set GEMINI_API_KEY in .env. Get key at https://aistudio.google.com/apikey")

        _models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        _current = cfg["ai"].get("model", "gemini-1.5-pro")
        if _current not in _models:
            _models.insert(0, _current)
        ai_model = st.selectbox("Model", _models, index=_models.index(_current), key="ai_model")
        ai_thr = st.slider("Confidence threshold", 0, 100, int(cfg["ai"]["confidence_threshold"]), key="ai_thr")
        ml_thr = st.slider("ML probability threshold", 0.0, 1.0, float(cfg["ai"]["ml_probability_threshold"]), 0.01, key="ai_ml_thr")
        ai_temp = st.slider("Temperature", 0.0, 1.0, float(cfg["ai"].get("temperature", 0.2)), 0.05, key="ai_temp")
        ai_prompt = st.text_area("System prompt override (blank = default)",
                                 cfg["ai"].get("system_prompt_override", ""), height=160, key="ai_prompt")

    # ---- Validators -------------------------------------------------------
    with tabs[6]:
        _section("External validators (online sources)")
        v_news_en = st.checkbox("News validator enabled",
                                bool(cfg.get("ai", {}).get("validators", {})
                                     .get("news_enabled", True)),
                                key="val_news_en")
        v_sent_en = st.checkbox("Web sentiment validator enabled (Gemini + Google Search)",
                                bool(cfg.get("ai", {}).get("validators", {})
                                     .get("sentiment_enabled", True)),
                                key="val_sent_en")
        v_sent_min = st.slider("Min sentiment score to allow trade", 0, 100,
                               int(cfg.get("ai", {}).get("validators", {})
                                   .get("sentiment_min_score", 60)),
                               key="val_sent_min")
        v_use_search = st.checkbox("Allow AI to use web search grounding",
                                   bool(cfg.get("ai", {}).get("use_web_search", True)),
                                   key="val_use_search")
        st.divider()
        _section("Strategy gates that block trades")
        s_req_news = st.checkbox("Require news clear",
                                 bool(cfg["strategy"].get("require_news_clear", True)),
                                 key="strat_req_news")
        s_req_sent = st.checkbox("Require sentiment alignment",
                                 bool(cfg["strategy"].get("require_sentiment_align", True)),
                                 key="strat_req_sent")
        s_req_vol = st.checkbox("Require volume confirmation",
                                bool(cfg["strategy"].get("require_volume_confirm", True)),
                                key="strat_req_vol")

    # ---- Localization -----------------------------------------------------
    with tabs[7]:
        _section("Display preferences")
        cur = (cfg.get("ui", {}).get("display_currency", "ZAR") or "ZAR").upper()
        loc_currency = st.selectbox(
            "Display currency",
            ["ZAR", "USD"],
            index=["ZAR", "USD"].index(cur if cur in ("ZAR", "USD") else "ZAR"),
            key="loc_currency",
            help="All money values in the dashboard will be shown in this currency. "
                 "ZAR uses the live USD/ZAR rate.",
        )
        wr_target = st.number_input(
            "Win-rate target (%)",
            min_value=50, max_value=99,
            value=int(cfg.get("user_targets", {}).get("win_rate_target", 90)),
            key="loc_wr_target",
            help="Aspirational target shown in reports. Realistic ceiling for retail FX is ~70-80%.",
        )

    # ---- ML ----------------------------------------------------------------
    with tabs[8]:
        _section("Machine Learning")
        ml_enabled = st.checkbox("ML enabled", bool(cfg["ml"]["enabled"]))
        ml_min = st.number_input("Min trades to train", 50, 5000, int(cfg["ml"]["min_samples_to_train"]))
        ml_n = st.number_input("n_estimators", 50, 1000, int(cfg["ml"]["n_estimators"]))
        ml_depth = st.number_input("max_depth", 3, 50, int(cfg["ml"]["max_depth"]))

    # ---- News --------------------------------------------------------------
    with tabs[9]:
        _section("News filter")
        st.write("News-block windows are managed under **Prop firm** tab.")

    # ---- Notifications -----------------------------------------------------
    with tabs[10]:
        _section("Telegram notifications")
        n_enabled = st.checkbox("Telegram enabled", bool(cfg["notifications"]["telegram_enabled"]))
        cols = st.columns(2)
        toggles = {}
        for i, k in enumerate([k for k in cfg["notifications"] if k != "telegram_enabled"]):
            with cols[i % 2]:
                toggles[k] = st.checkbox(k.replace("_", " "), bool(cfg["notifications"][k]))

    # ---- Instruments -------------------------------------------------------
    with tabs[11]:
        _section("Instruments")
        new_instr = {}
        for sym, meta in cfg.get("instruments", {}).items():
            with st.expander(sym, expanded=False):
                cc1, cc2, cc3, cc4 = st.columns(4)
                en = cc1.checkbox(f"{sym} enabled", bool(meta.get("enabled", True)), key=f"en_{sym}")
                mx = cc2.number_input("Max lot", 0.01, 100.0, float(meta.get("max_lot", 1.0)), 0.1, key=f"mx_{sym}")
                pv = cc3.number_input("Pip value (USD)", 0.01, 1000.0, float(meta.get("pip_value_usd", 10.0)), 0.1, key=f"pv_{sym}")
                dg = cc4.number_input("Digits", 0, 6, int(meta.get("digits", 5)), key=f"dg_{sym}")
                new_instr[sym] = {"enabled": en, "max_lot": mx, "pip_value_usd": pv, "digits": dg}

    st.divider()
    if st.button("💾 Save settings", type="primary", use_container_width=True):
        cfg["bot"].update(mode=mode, scan_interval_minutes=int(scan), active_sessions=sessions,
                          pairs=pairs, primary_timeframe=primary, trend_timeframe=trend_tf)
        cfg["strategy"].update(name=strat_name, min_confluence_score=int(min_conf),
                               min_rr=float(min_rr), target_rr=float(target_rr),
                               require_mtf_alignment=require_mtf, use_pattern_filter=use_pat,
                               use_session_filter=use_sess,
                               require_news_clear=bool(st.session_state.get("strat_req_news", True)),
                               require_sentiment_align=bool(st.session_state.get("strat_req_sent", True)),
                               require_volume_confirm=bool(st.session_state.get("strat_req_vol", True)),
                               custom_rules=[r.strip() for r in st.session_state.get("strategy_rules","").splitlines() if r.strip()])
        cfg["user_targets"].update(profit_target_pct=float(profit_target), max_days_to_target=int(max_days),
                                   max_trades_per_day=int(max_per_day),
                                   preferred_pairs=preferred_pairs, preferred_sessions=preferred_sessions)
        cfg["risk"].update(risk_pct_per_trade=float(risk_pct), max_concurrent_trades=int(max_conc),
                           max_daily_trades=int(max_daily), max_spread_pips=float(max_spread),
                           daily_loss_limit_pct=float(daily_loss), max_drawdown_pct=float(max_dd),
                           kill_switch_warning_pct=int(warn_pct),
                           atr_sl_multiplier=float(atr_sl), atr_tp_multiplier=float(atr_tp),
                           breakeven_at_r=float(be_r), partial_close_at_r=float(partial_r),
                           partial_close_pct=int(partial_pct))
        cfg["prop_firm"].update(profile=profile, daily_loss_limit_pct=float(pf_daily),
                                max_drawdown_pct=float(pf_dd),
                                news_block_before_min=int(pf_news_b), news_block_after_min=int(pf_news_a))
        cfg["ai"].update(backend=ai_backend, model=ai_model,
                         vertex_project=vertex_project, vertex_location=vertex_location,
                         confidence_threshold=int(ai_thr),
                         ml_probability_threshold=float(ml_thr), temperature=float(ai_temp),
                         system_prompt_override=ai_prompt,
                         use_web_search=bool(st.session_state.get("val_use_search", True)))
        cfg["ai"].setdefault("validators", {}).update(
            news_enabled=bool(st.session_state.get("val_news_en", True)),
            sentiment_enabled=bool(st.session_state.get("val_sent_en", True)),
            sentiment_min_score=int(st.session_state.get("val_sent_min", 60)),
        )
        cfg.setdefault("ui", {})["display_currency"] = st.session_state.get("loc_currency", "ZAR")
        cfg["user_targets"]["win_rate_target"] = int(st.session_state.get("loc_wr_target", 90))
        cfg["ml"].update(enabled=bool(ml_enabled), min_samples_to_train=int(ml_min),
                         n_estimators=int(ml_n), max_depth=int(ml_depth))
        cfg["notifications"]["telegram_enabled"] = bool(n_enabled)
        for k, v in toggles.items():
            cfg["notifications"][k] = bool(v)
        cfg["instruments"] = new_instr or cfg["instruments"]
        s.save(cfg)
        get_state().update(mode=mode)
        try:
            from journal.db import log_audit
            log_audit("settings_save",
                      actor=st.session_state.get("auth_username"),
                      target="config.json")
        except Exception:                                  # noqa: BLE001
            pass
        try:
            from ai.gemini import reset_client
            reset_client()
        except Exception:                                  # noqa: BLE001
            pass
        st.success("Settings saved and applied live.")
