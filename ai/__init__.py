"""AI package — Gemini reasoning layer."""
from .gemini import evaluate_signal, HAS_GEMINI
from .prompts import SYSTEM_PROMPT, build_decision_prompt

__all__ = ["evaluate_signal", "HAS_GEMINI", "SYSTEM_PROMPT", "build_decision_prompt"]
