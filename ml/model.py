"""
Random Forest signal-quality classifier.

Saves models to ml/models/ as `rf_<timestamp>.pkl` and a `rf_latest.pkl`
symlink-style copy for fast loading at runtime.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from config.settings import ML_MODEL_DIR, get_settings
from journal.db import insert
from ml.features import FEATURES, build_training_set, signal_to_features
from utils.helpers import utcnow_iso
from utils.logging import logger

LATEST_MODEL: Path = ML_MODEL_DIR / "rf_latest.pkl"
_MODEL_CACHE: dict[str, Any] = {"model": None, "loaded_path": None}


def train_model() -> dict[str, Any] | None:
    s = get_settings()
    X, y = build_training_set()
    min_n = int(s.get("ml.min_samples_to_train", 100))
    if len(X) < min_n:
        logger.warning(f"Not enough data to train ML ({len(X)}/{min_n})")
        return None

    test_size = float(s.get("ml.test_size", 0.2))
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y if y.nunique() > 1 else None, random_state=42,
    )

    clf = RandomForestClassifier(
        n_estimators=int(s.get("ml.n_estimators", 300)),
        max_depth=int(s.get("ml.max_depth", 12)),
        random_state=42, n_jobs=-1, class_weight="balanced",
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    metrics = {
        "accuracy":  float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall":    float(recall_score(y_test, y_pred, zero_division=0)),
        "f1":        float(f1_score(y_test, y_pred, zero_division=0)),
    }

    fi = dict(zip(FEATURES, [float(v) for v in clf.feature_importances_]))
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = ML_MODEL_DIR / f"rf_{stamp}.pkl"
    joblib.dump({"model": clf, "features": FEATURES, "metrics": metrics, "trained_at": utcnow_iso()}, fname)
    joblib.dump({"model": clf, "features": FEATURES, "metrics": metrics, "trained_at": utcnow_iso()}, LATEST_MODEL)

    insert("ml_runs", {
        "trained_at": utcnow_iso(),
        "model_file": str(fname),
        "n_samples": int(len(X)),
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "feature_importance": json.dumps(fi),
    })
    _MODEL_CACHE["model"] = None
    logger.success(f"ML model retrained {metrics} → {fname.name}")
    return {"file": str(fname), "metrics": metrics, "feature_importance": fi}


def load_model() -> dict[str, Any] | None:
    if _MODEL_CACHE["model"] is not None:
        return _MODEL_CACHE["model"]
    if not LATEST_MODEL.exists():
        return None
    try:
        bundle = joblib.load(LATEST_MODEL)
        _MODEL_CACHE["model"] = bundle
        _MODEL_CACHE["loaded_path"] = str(LATEST_MODEL)
        return bundle
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"Failed to load ML model: {exc}")
        return None


def score_signal(signal: dict) -> float | None:
    """Return win-probability ∈ [0,1], or None if no model is available."""
    if not get_settings().get("ml.enabled", True):
        return None
    bundle = load_model()
    if not bundle:
        return None
    try:
        X = signal_to_features(signal)
        model = bundle["model"]
        return float(model.predict_proba(X[bundle["features"]])[0][1])
    except Exception as exc:                               # noqa: BLE001
        logger.exception(f"ML score failed: {exc}")
        return None


def feature_importance() -> dict[str, float]:
    bundle = load_model()
    if not bundle:
        return {}
    return dict(zip(bundle["features"], bundle["model"].feature_importances_.tolist()))


def latest_metrics() -> dict[str, Any] | None:
    bundle = load_model()
    return bundle.get("metrics") if bundle else None
