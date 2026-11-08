"""JSON helpers for the API: DataFrames and Chart objects -> plain JSON (NaN/NaT -> null, Timestamps -> ISO strings)."""
from __future__ import annotations

import datetime as dt
import json
import math
from decimal import Decimal

import numpy as np
import pandas as pd

from ..viz import common as C

MAX_ROWS = 5000


def scalar(v):
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.isoformat(sep=" ") if not pd.isna(v) else None
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (list, tuple, set, np.ndarray)):
        return [scalar(x) for x in v]
    if isinstance(v, dict):
        return {str(k): scalar(x) for k, x in v.items()}
    return v


def records(df: pd.DataFrame, limit: int | None = MAX_ROWS) -> list[dict]:
    if df is None or len(df) == 0:
        return []
    d = df.head(limit) if limit else df
    d = d.astype(object).where(d.notna(), None)
    cols = [str(c) for c in d.columns]
    return [{c: scalar(v) for c, v in zip(cols, row)} for row in d.itertuples(index=False, name=None)]


def table(df: pd.DataFrame, limit: int | None = MAX_ROWS) -> dict:
    return {"columns": [str(c) for c in (df.columns if df is not None else [])], "rows": records(df, limit), "total": 0 if df is None else int(len(df))}


def chart_payload(c: C.Chart) -> dict:
    out = {"name": c.name, "available": bool(c.available), "reason": c.reason, "n": int(c.n or 0), "unit": C.unit_for(c.name), "source": c.source, "note": c.note,
           "hasStatic": c.static is not None, "data": table(c.data), "figure": None}
    if c.available and c.fig is not None:
        out["figure"] = json.loads(c.fig.to_json())
    return out
