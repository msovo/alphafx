"""
External validators for high-conviction signal gating.

Two validators:
  1. `news_clear(signal)`     — checks economic-calendar blackout window
                                  and recent breaking-news risk.
  2. `web_sentiment(signal)`  — uses Gemini with Google Search grounding
                                  to assess online sentiment / recent
                                  headlines that align (or contradict)
                                  the trade direction.

Both return dicts:
   { "ok": bool, "score": int 0-100, "reason": str, "sources": [ ... ] }

Designed to be called from `core.pipeline.run_signal_scan` AFTER
the AI decision but BEFORE risk checks.  Any "ok=False" blocks the trade.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from config.settings import get_settings
from data.news import is_news_blackout, upcoming_high_impact, _symbol_currencies
from utils.logging import logger

try:
    from google import genai                              # type: ignore
    from google.genai import types as genai_types         # type: ignore
    HAS_GENAI = True
except Exception:                                          # noqa: BLE001
    HAS_GENAI = False


# ---------------------------------------------------------------------------
# 1) News validator
# ---------------------------------------------------------------------------
def news_clear(signal: dict) -> dict:
    """Block the signal if a high-impact event is inside the blackout window."""
    s = get_settings()
    before = int(s.get("prop_firm.news_block_before_min", 45))
    after = int(s.get("prop_firm.news_block_after_min", 30))
    pair = signal.get("pair", "")
    blocked, ev = is_news_blackout(pair, before_min=before, after_min=after)
    if blocked and ev:
        return {
            "ok": False, "score": 0,
            "reason": f"News blackout: {ev['currency']} {ev['title']} "
                      f"@ {ev['datetime_utc'].strftime('%H:%M UTC')}",
            "sources": [],
        }
    # Soft warning if a high-impact event is within 4h
    upcoming = upcoming_high_impact(within_hours=4,
                                    currencies=list(_symbol_currencies(pair)))
    if upcoming:
        ev = upcoming[0]
        mins = int((ev["datetime_utc"].timestamp() - time.time()) / 60)
        if mins <= 90:
            return {
                "ok": True, "score": 55,
                "reason": f"High-impact in {mins}min — caution",
                "sources": [f"{ev['currency']} {ev['title']}"],
            }
    return {"ok": True, "score": 90, "reason": "No high-impact news nearby", "sources": []}


# ---------------------------------------------------------------------------
# 2) Web sentiment validator (Gemini + Google Search grounding)
# ---------------------------------------------------------------------------
_PROMPT = """You are a senior FX market analyst with web search access.

Search the latest news, central-bank statements, and social-trader chatter
(last 24-48 hours) for **{pair}** and judge whether they SUPPORT a
**{direction}** trade.

Return STRICT JSON only:
{{
  "score": <0-100, 100 = fully supports {direction}>,
  "sentiment": "bullish" | "bearish" | "mixed" | "unclear",
  "headlines": ["short summary 1", "short summary 2", "..."],
  "reason": "<= 200 chars, plain english",
  "risk": "low" | "medium" | "high"
}}

Be skeptical. If headlines contradict the trade direction, score < 40.
If no clear consensus, score 40-60.  Only score > 70 if multiple
independent recent items align with the trade.
"""


def _build_search_client():
    if not HAS_GENAI:
        return None, None
    s = get_settings()
    backend = (s.ai_backend or "studio").lower()
    try:
        if backend == "vertex":
            if not s.vertex_project:
                return None, None
            client = genai.Client(vertexai=True, project=s.vertex_project,
                                  location=s.vertex_location or "us-central1")
        else:
            if not s.gemini_api_key:
                return None, None
            client = genai.Client(api_key=s.gemini_api_key)
        return client, s.gemini_model
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"sentiment client init failed: {exc}")
        return None, None


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    raw = re.sub(r"^```(json)?", "", raw.strip()).rstrip("`").strip()
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


def web_sentiment(signal: dict) -> dict:
    """Use Gemini with Google Search grounding to validate via online news."""
    s = get_settings()
    if not s.get("ai.use_web_search", True):
        return {"ok": True, "score": 65, "reason": "Web search disabled", "sources": []}

    client, model = _build_search_client()
    if client is None:
        return {"ok": True, "score": 60, "reason": "AI client unavailable — skipped",
                "sources": []}

    prompt = _PROMPT.format(pair=signal["pair"], direction=signal["direction"])
    try:
        # Google Search grounding tool (Vertex + Studio supported on 2.0+ models)
        search_tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
        cfg = genai_types.GenerateContentConfig(
            tools=[search_tool],
            temperature=0.2,
            system_instruction=(
                "You are a sharp FX research analyst. Prefer reputable "
                "sources (Reuters, Bloomberg, FT, ForexFactory, central banks)."
            ),
        )
        resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
        text = (resp.text or "").strip() if resp else ""
        sources: list[str] = []
        try:
            cands = getattr(resp, "candidates", []) or []
            for c in cands:
                gm = getattr(c, "grounding_metadata", None)
                if gm and getattr(gm, "grounding_chunks", None):
                    for ch in gm.grounding_chunks:
                        web = getattr(ch, "web", None)
                        if web and getattr(web, "uri", None):
                            sources.append(getattr(web, "title", "") or web.uri)
        except Exception:                                   # noqa: BLE001
            pass

        parsed = _parse_json(text) or {}
        score = int(parsed.get("score", 50))
        score = max(0, min(100, score))
        min_score = int(s.get("ai.validators.sentiment_min_score", 60))
        ok = score >= min_score
        return {
            "ok": ok, "score": score,
            "sentiment": parsed.get("sentiment", "unclear"),
            "reason": str(parsed.get("reason", ""))[:200],
            "headlines": parsed.get("headlines", [])[:5],
            "sources": sources[:5],
        }
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"web_sentiment failed: {exc}")
        # Don't block on infra failure — pass with neutral score
        return {"ok": True, "score": 55, "reason": f"sentiment unavailable: {exc}",
                "sources": []}


# ---------------------------------------------------------------------------
# Composite gate
# ---------------------------------------------------------------------------
def validate_signal(signal: dict) -> tuple[bool, dict]:
    """Run all enabled validators; returns (passed, report)."""
    s = get_settings()
    report: dict[str, Any] = {}
    passed = True

    if s.get("ai.validators.news_enabled", True) and s.get("strategy.require_news_clear", True):
        rep = news_clear(signal)
        report["news"] = rep
        if not rep["ok"]:
            passed = False

    if (passed
            and s.get("ai.validators.sentiment_enabled", True)
            and s.get("strategy.require_sentiment_align", True)):
        rep = web_sentiment(signal)
        report["sentiment"] = rep
        if not rep["ok"]:
            passed = False

    return passed, report
