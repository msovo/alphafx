"""
Google Gemini reasoning layer — supports both modes via `AI_BACKEND`:

- `studio` (default): uses GEMINI_API_KEY against Google AI Studio
- `vertex`: uses Google Cloud Vertex AI (works with free GCP credit)
            Requires:  gcloud auth application-default login
            Plus env:  VERTEX_PROJECT, VERTEX_LOCATION (e.g. us-central1)

`evaluate_signal(signal)` returns a dict with the standard decision schema.
Falls back to a deterministic "skip" if the API is unavailable.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from ai.prompts import SYSTEM_PROMPT, build_decision_prompt
from config.settings import get_settings
from core.broker import get_broker
from core.state import get_state
from data.news import upcoming_high_impact
from journal.db import query
from journal.logger import log_ai
from utils.logging import logger

try:
    from google import genai                              # type: ignore
    from google.genai import types as genai_types         # type: ignore
    HAS_GENAI = True
except Exception:                                          # noqa: BLE001
    genai = None                                           # type: ignore
    genai_types = None                                     # type: ignore
    HAS_GENAI = False

# Backwards-compatible alias used by other modules.
HAS_GEMINI = HAS_GENAI


_DEFAULT = {
    "decision": "skip", "confidence": 0,
    "reason": "AI unavailable — defaulted to skip",
    "suggested_adjustment": "", "risk_flag": "high",
    "ai_unavailable": True,
}

_client = None  # type: ignore


def _build_client():
    """Build a cached Gemini client based on AI_BACKEND."""
    global _client
    if _client is not None:
        return _client
    if not HAS_GENAI:
        return None
    s = get_settings()
    backend = (s.ai_backend or "studio").lower()
    try:
        if backend == "vertex":
            project = s.vertex_project
            location = s.vertex_location or "us-central1"
            if not project:
                logger.warning("VERTEX_PROJECT not set; cannot use Vertex backend")
                return None
            _client = genai.Client(vertexai=True, project=project, location=location)
            logger.info(f"Gemini client: Vertex AI (project={project}, location={location})")
        else:
            key = s.gemini_api_key
            if not key:
                logger.warning("GEMINI_API_KEY not set; cannot use Studio backend")
                return None
            _client = genai.Client(api_key=key)
            logger.info("Gemini client: AI Studio (API key)")
        return _client
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"Gemini client init failed: {exc}")
        return None


def reset_client() -> None:
    """Drop the cached client so the next call rebuilds it (after settings change)."""
    global _client
    _client = None


def _build_context(signal: dict) -> dict[str, Any]:
    s = get_settings()
    state = get_state().state
    info = get_broker().account_info()
    recent = query(
        "SELECT pair, direction, pnl_usd, outcome FROM trades "
        "WHERE status='closed' ORDER BY close_time DESC LIMIT 5"
    )
    news = upcoming_high_impact(within_hours=4)
    return {
        "equity": getattr(info, "equity", 0.0),
        "balance": getattr(info, "balance", 0.0),
        "daily_pnl": state.daily_pnl,
        "daily_dd_pct": state.daily_dd_pct,
        "total_dd_pct": state.total_dd_pct,
        "open_positions": state.open_positions,
        "recent_trades": recent.to_dict("records") if not recent.empty else [],
        "upcoming_news": [
            f"{e['datetime_utc'].strftime('%H:%M')} {e['currency']} {e['title']}"
            for e in news
        ],
        "prop_firm_rules": {
            "daily_loss_limit_pct": s.get("prop_firm.daily_loss_limit_pct", 5.0),
            "max_drawdown_pct": s.get("prop_firm.max_drawdown_pct", 10.0),
        },
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _validate(payload: dict[str, Any]) -> dict[str, Any]:
    decision = str(payload.get("decision", "skip")).lower()
    if decision not in {"trade", "skip", "wait"}:
        decision = "skip"
    confidence = int(payload.get("confidence", 0))
    confidence = max(0, min(100, confidence))
    flag = str(payload.get("risk_flag", "none")).lower()
    if flag not in {"none", "caution", "high"}:
        flag = "none"
    return {
        "decision": decision,
        "confidence": confidence,
        "reason": str(payload.get("reason", ""))[:500],
        "suggested_adjustment": str(payload.get("suggested_adjustment", ""))[:240],
        "risk_flag": flag,
    }


def _generate(model_name: str, system_instruction: str, prompt: str,
              temperature: float, json_mode: bool,
              max_tokens: int | None = None) -> tuple[str, str | None]:
    """Run a single generate_content call. Returns (text, error_or_none)."""
    client = _build_client()
    if client is None:
        return "", "client_unavailable"
    try:
        cfg_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction,
            "temperature": temperature,
        }
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"
        if max_tokens:
            cfg_kwargs["max_output_tokens"] = max_tokens
        config = genai_types.GenerateContentConfig(**cfg_kwargs)
        resp = client.models.generate_content(
            model=model_name, contents=prompt, config=config,
        )
        text = (resp.text or "").strip() if resp else ""
        return text, None
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"Gemini generate failed ({model_name}): {exc}")
        return "", str(exc)


def evaluate_signal(signal: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    model_name = s.gemini_model
    prompt = build_decision_prompt(signal, _build_context(signal))
    system = s.get("ai.system_prompt_override") or SYSTEM_PROMPT

    start = time.time()
    text, err = _generate(
        model_name=model_name,
        system_instruction=system,
        prompt=prompt,
        temperature=float(s.get("ai.temperature", 0.2)),
        json_mode=True,
    )
    latency = int((time.time() - start) * 1000)

    parsed = _parse_json(text) or {}
    result = _validate(parsed) if parsed else _DEFAULT.copy()
    if err:
        result["reason"] = (result.get("reason") or "") + f" [api_error: {err[:120]}]"
        result["ai_unavailable"] = True

    log_ai(prompt, text or "", signal_id=signal.get("signal_id"),
           model=model_name, latency_ms=latency, error=err)
    return result


# ---------------------------------------------------------------------------
# Free-form market commentary (used by the Charts page)
# ---------------------------------------------------------------------------
def commentary(symbol: str, timeframe: str, snapshot: dict) -> str:
    """Plain-English explanation of the current chart state."""
    s = get_settings()
    prompt = (
        f"You are a senior FX trader. In 4-6 sentences, explain what's happening on "
        f"{symbol} ({timeframe}) using the data below. Cover: trend bias (HTF + LTF), "
        f"momentum, key levels nearby, volatility regime, and one actionable observation. "
        f"Plain English, no fluff, no disclaimers.\n\n"
        f"Snapshot JSON:\n{json.dumps(snapshot, default=str)}"
    )
    text, err = _generate(
        model_name=s.gemini_model,
        system_instruction="You are a concise, sharp FX market analyst.",
        prompt=prompt,
        temperature=0.4,
        json_mode=False,
        max_tokens=400,
    )
    if err:
        return f"Commentary unavailable: {err}"
    return text or "(empty response)"
