"""Streamlit helpers for the visualisation pages: cached loaders, the shared filter sidebar, chart rendering with table view + downloads, cross-filtering."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..analysis import data as D
from ..viz import common as C
from ..viz import export
from ..viz.filters import Filters, apply_matches, apply_team_matches
from . import queries as Q

PLOTLY_CONFIG = lambda name: {"displaylogo": False, "responsive": True, "toImageButtonOptions": {"format": "png", "filename": name, "scale": 2}}


# ------------------------------------------------------------------ cached loaders (5-10 min)
@st.cache_data(ttl=600, show_spinner="Loading matches…")
def matches_played() -> pd.DataFrame:
    return D.matches()


@st.cache_data(ttl=600, show_spinner=False)
def matches_all() -> pd.DataFrame:
    return D.matches(played_only=False)


@st.cache_data(ttl=600, show_spinner=False)
def team_matches() -> pd.DataFrame:
    return D.team_matches()


@st.cache_data(ttl=600, show_spinner=False)
def tournaments() -> pd.DataFrame:
    return D.tournaments()


@st.cache_data(ttl=600, show_spinner=False)
def goals() -> pd.DataFrame:
    return D.goals()


@st.cache_data(ttl=600, show_spinner=False)
def standings() -> pd.DataFrame:
    from ..viz.competition import load_standings
    return load_standings()


@st.cache_data(ttl=600, show_spinner=False)
def player_seasons() -> pd.DataFrame:
    return D.player_seasons()


@st.cache_data(ttl=600, show_spinner="Reading event-level player statistics…")
def player_stats() -> pd.DataFrame:
    from ..ml.clustering import player_stat_table
    return player_stat_table()


@st.cache_data(ttl=600, show_spinner=False)
def reliable_seasons() -> set[str]:
    return set(D.q("select distinct s.season_id from wh.fact_match_events e join wh.fact_matches m using (match_key) join wh.dim_season s using (season_key) where e.provider='statsbomb'").season_id)


@st.cache_data(ttl=600, show_spinner="Computing the contribution index…")
def contribution_index() -> pd.DataFrame:
    from ..analysis.advanced import player_contribution
    return player_contribution()


@st.cache_data(ttl=600, show_spinner=False)
def team_country() -> dict:
    from ..viz.matches import team_country as tc
    return tc()


@st.cache_data(ttl=3600, show_spinner="Scoring the test period with the saved models…")
def outcome_test():
    from ..viz import mlplots
    t = mlplots.load_outcome_test()
    return t


@st.cache_data(ttl=3600, show_spinner=False)
def goal_test():
    from ..viz import mlplots
    return mlplots.load_goal_test()


@st.cache_data(ttl=3600, show_spinner="Computing SHAP values…")
def shap_values():
    from ..viz import mlplots
    return mlplots.load_shap()


# ------------------------------------------------------------------ filters
def sidebar_filters(matches: pd.DataFrame, show_teams: bool = True, show_stages: bool = True) -> Filters:
    """One filter block for every visualisation page (state is shared through st.session_state keys)."""
    sb = st.sidebar
    sb.header("Filters")
    comps = sb.multiselect("Competition", C.COMPS, format_func=lambda c: C.COMP_LABEL[c], key="f_comps", help="empty = all four competitions")
    m = matches[matches.competition_id.isin(comps)] if comps else matches
    seasons = sb.multiselect("Edition / season", sorted(m.season_id.unique()), key="f_seasons", help="empty = every edition of the selected competitions")
    stages_all = [s for s in ["Group stage", "Play-off", "Promotion/relegation play-off", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Third place", "Final"] if s in set(m.stage_name)]
    stages = sb.multiselect("Tournament stage", stages_all, key="f_stages") if show_stages else []
    teams = sb.multiselect("Team", sorted(set(m.home_team_name.dropna()) | set(m.away_team_name.dropna())), key="f_teams", help="a match is kept when any selected team plays in it") if show_teams else []
    dmin, dmax = pd.to_datetime(matches.match_date).min().date(), pd.to_datetime(matches.match_date).max().date()
    rng = sb.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax, key="f_dates")
    d0, d1 = (rng if isinstance(rng, (tuple, list)) and len(rng) == 2 else (dmin, dmax))
    f = Filters(competitions=comps, seasons=seasons, stages=stages, teams=teams, date_from=pd.Timestamp(d0) if d0 != dmin else None, date_to=pd.Timestamp(d1) if d1 != dmax else None)
    sb.caption("Showing: " + f.describe())
    if sb.button("Reset filters"):
        for k in ("f_comps", "f_seasons", "f_stages", "f_teams", "f_dates"):
            st.session_state.pop(k, None)
        st.rerun()
    return f


def filtered_download(df: pd.DataFrame, name: str, label: str = "Download the filtered matches (CSV)"):
    st.sidebar.download_button(label, export.csv_bytes(df), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")


# ------------------------------------------------------------------ chart rendering
def render(chart: C.Chart, key: str, select: bool = False):
    """Draw a chart (or explain why it is not drawn), then its sample size / source / limitations, a table view and the downloads.
    Returns the Streamlit selection event when select=True (used for cross-filtering)."""
    if not chart.available:
        st.info(f"**Not shown:** {chart.reason}")
        return None
    ev = st.plotly_chart(chart.fig, use_container_width=True, key=key, config=PLOTLY_CONFIG(chart.name), on_select="rerun" if select else "ignore", selection_mode=("points",) if select else ())
    st.caption(C.table_note(chart))
    with st.expander("Table view and downloads"):
        st.dataframe(chart.data, hide_index=True, use_container_width=True)
        c = st.columns(3)
        c[0].download_button("CSV (data behind the chart)", export.csv_bytes(chart.data), file_name=export.filename(chart, "csv"), mime="text/csv", key=f"{key}_csv")
        h = export.html_bytes(chart)
        if h:
            c[1].download_button("Interactive HTML", h, file_name=export.filename(chart, "html"), mime="text/html", key=f"{key}_html")
        png, how = export.png_bytes(chart)
        if png:
            c[2].download_button("PNG (Matplotlib/Seaborn)" if how == "matplotlib" else "PNG", png, file_name=export.filename(chart, "png"), mime="image/png", key=f"{key}_png")
        else:
            c[2].caption("PNG: use the camera icon in the chart toolbar.")
    return ev


def selected(ev, field: str = "x") -> list:
    """Values of `field` for the points the user clicked/selected on a chart (cross-filtering)."""
    try:
        pts = ev.selection.points if ev is not None else []
    except Exception:
        pts = []
    return [p.get(field) for p in pts if p.get(field) is not None]


def sample_banner(n_played: int, n_total: int, what: str = "matches"):
    st.caption(f"**{n_played:,}** of {n_total:,} {what} in the current selection (played matches only; 'Coming soon' fixtures are never part of statistics).")
