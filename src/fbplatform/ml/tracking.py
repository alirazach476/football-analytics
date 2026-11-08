"""MLflow tracking (local SQLite store, no server needed) + model saving. Open the UI with:  mlflow ui --backend-store-uri sqlite:///mlflow.db"""
from __future__ import annotations

import json
import platform
from contextlib import contextmanager
from datetime import datetime, timezone

import joblib
import mlflow
import numpy as np
import pandas as pd

from ..config import ROOT

MODELS = ROOT / "models"
REPORTS = ROOT / "reports" / "ml"
URI = f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}"


def _clean(v):
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v


@contextmanager
def run(experiment: str, name: str, params: dict | None = None, tags: dict | None = None):
    mlflow.set_tracking_uri(URI)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=name) as r:
        mlflow.set_tags({"python": platform.python_version(), **(tags or {})})
        if params:
            mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        yield r


def log_metrics(metrics: dict, prefix: str = ""):
    mlflow.log_metrics({f"{prefix}{k}": float(_clean(v)) for k, v in metrics.items() if v is not None and np.isfinite(float(_clean(v)))})


def save_model(model, name: str, meta: dict) -> str:
    MODELS.mkdir(exist_ok=True)
    path = MODELS / f"{name}.joblib"
    joblib.dump(model, path)
    meta = {**meta, "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "python": platform.python_version()}
    (MODELS / f"{name}.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    return str(path)


def save_table(df: pd.DataFrame, name: str, sub: str = "") -> str:
    d = REPORTS / sub if sub else REPORTS
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.csv"
    df.to_csv(p, index=False)
    return str(p)
