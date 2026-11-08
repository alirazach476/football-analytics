"""Shared Streamlit helpers: cached queries, consistent colours/layout, standard banners."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ..analysis.data import COMP_COLOR, COMP_NAME
from . import queries as Q

LAYOUT = dict(template="plotly_white", font=dict(family="Inter, Segoe UI, sans-serif", size=13), margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.25))
OUTCOME_COLORS = {"team listed first wins": "#0072B2", "draws": "#999999", "team listed second wins": "#D55E00"}


@st.cache_data(ttl=300, show_spinner=False)
def cached(fn_name: str, *args):
    return getattr(Q, fn_name)(*args)


def require_db():
    if not Q.db_available():
        st.error("The PostgreSQL warehouse is not reachable. Start it with `docker compose up -d`, then run `python -m fbplatform.orchestration.steps`.")
        st.stop()


def fig(f, key=None):
    st.plotly_chart(f.update_layout(**LAYOUT), use_container_width=True, key=key)


def coming_soon_note(n: int):
    if n:
        st.info(f"**Coming soon:** {n} fixtures are scheduled and not played yet. They are listed with whatever is known (date, stage, venue) and have no results.")


def prediction_banner():
    st.warning("Everything labelled **prediction** below is model output made without knowing the result. It is not an actual result and not betting advice.", icon="⚠️")


def comp_selector(key="comp"):
    comps = cached("competitions")
    label = {r.competition_id: r.competition_name for r in comps.itertuples()}
    c = st.sidebar.selectbox("Competition", list(label), format_func=lambda x: label[x], key=key)
    return c, label[c]
