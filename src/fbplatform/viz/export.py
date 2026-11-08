"""Export helpers (no Streamlit): CSV of the data behind a chart, standalone HTML of the interactive chart, PNG when it can be produced.
PNG strategy: Matplotlib/Seaborn twin when the chart has one (`Chart.static`); otherwise Plotly+kaleido if installed; otherwise None (the browser's
camera button in the chart toolbar still downloads a PNG of the interactive chart)."""
from __future__ import annotations

import io

import pandas as pd

from .common import Chart


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def html_bytes(chart: Chart) -> bytes | None:
    if not chart.available or chart.fig is None:
        return None
    return chart.fig.to_html(include_plotlyjs=True, full_html=True).encode("utf-8")


def png_bytes(chart: Chart) -> tuple[bytes | None, str]:
    """-> (png or None, how). how in {'matplotlib', 'kaleido', 'unavailable'}."""
    if not chart.available:
        return None, "unavailable"
    if chart.static is not None:
        import matplotlib
        import matplotlib.pyplot as plt
        matplotlib.use("Agg", force=False)
        f = chart.static()
        buf = io.BytesIO()
        f.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
        plt.close(f)
        return buf.getvalue(), "matplotlib"
    try:
        import kaleido  # noqa: F401
        return chart.fig.to_image(format="png", scale=2), "kaleido"
    except Exception:
        return None, "unavailable"


def filename(chart: Chart, ext: str) -> str:
    return f"{chart.name}.{ext}"
