"""FastAPI backend of the React dashboard.  Run:  uvicorn fbplatform.api.main:app --port 8000   (needs PYTHONPATH=src and the warehouse running).
It exposes exactly what the Streamlit app used: the dashboard queries, every chart of the visualization lab (same functions, same data), tournament pages,
predictions from the saved models and exports. If frontend/dist exists it also serves the built React app."""
from __future__ import annotations

import io
import json
import re
import traceback

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ..analysis import data as D
from ..config import ROOT
from ..dashboard import queries as Q
from ..viz import common as C
from ..viz import export as X
from ..viz.filters import Filters
from . import charts, finalissima, store, tournaments, wc2030
from .serialize import chart_payload, records, scalar, table

app = FastAPI(title="Football analytics API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"], allow_methods=["*"], allow_headers=["*"])

QUERIES = ["kpis", "data_quality_score", "coverage_report", "upcoming_fixtures", "competitions", "edition_table", "outcome_table", "records", "goals_by_minute", "team_names", "team_summary", "team_by_edition",
           "team_results", "team_upcoming", "head_to_head_table", "player_search", "top_players", "player_by_edition", "player_awards", "player_profile", "season_ids", "match_search", "match_row",
           "match_timeline", "match_team_stats", "match_lineups", "pipeline_runs", "pipeline_summary", "ingestion_status", "dq_results", "duplicate_checks", "db_stats", "freshness",
           "ml_outcome_comparison", "ml_outcome_predictions", "ml_importance", "ml_goals", "ml_clusters", "ml_meta"]


def _jsonify(v):
    if isinstance(v, pd.DataFrame):
        return table(v)
    if isinstance(v, dict):
        return {k: _jsonify(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonify(x) for x in v]
    return scalar(v)


def _filters(d: dict | None) -> Filters:
    d = d or {}
    ts = lambda k: pd.Timestamp(d[k]) if d.get(k) else None
    return Filters(competitions=list(d.get("competitions") or []), seasons=list(d.get("seasons") or []), stages=list(d.get("stages") or []), teams=list(d.get("teams") or []),
                   date_from=ts("date_from"), date_to=ts("date_to"))


@app.exception_handler(KeyError)
async def _key_error(_, exc):
    return JSONResponse(status_code=404, content={"error": f"not found: {exc}"})


@app.exception_handler(Exception)
async def _any_error(_, exc):
    return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]})


@app.get("/api/health")
def health():
    ok = Q.db_available()
    return {"ok": ok, "database": "up" if ok else "down", "message": None if ok else "PostgreSQL warehouse not reachable: docker compose up -d, then python -m fbplatform.orchestration.steps"}


@app.get("/api/lookups")
def lookups():
    m = store.matches_all()
    tr = store.tournaments()
    stages = [s for s in ["Group stage", "Play-off", "Promotion/relegation play-off", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Third place", "Final"] if s in set(m.stage_name.dropna())]
    return {"competitions": [{"id": c, "label": C.COMP_LABEL[c], "color": C.COMP_COLOR[c]} for c in C.COMPS],
            "seasons": [{"seasonId": r.season_id, "competition": r.competition_id, "year": int(r.season_year), "status": "upcoming" if r.matches_played == 0 else "played"} for r in tr.itertuples()],
            "teams": sorted(set(m.home_team_name.dropna()) | set(m.away_team_name.dropna())), "stages": stages,
            "dateRange": [str(pd.to_datetime(m.match_date).min().date()), str(pd.to_datetime(m.match_date).max().date())],
            "reliableAssistSeasons": sorted(store.reliable_seasons()), "shotMapSeasons": ["WC-2018", "WC-2022", "EURO-2016", "EURO-2020", "EURO-2024", "COPA-2024"],
            "models": [k for k in (store.outcome_test() or {"proba": {}})["proba"]]}


@app.post("/api/query")
def query(body: dict = Body(...)):
    name, args = body.get("name"), body.get("args") or {}
    if name not in QUERIES:
        raise HTTPException(400, f"unknown query: {name}")
    fn = getattr(Q, name)
    return _jsonify(fn(**args))


@app.post("/api/chart")
def chart_endpoint(body: dict = Body(...)):
    c = charts.build(body["id"], _filters(body.get("filters")), body.get("params") or {})
    return chart_payload(c)


@app.post("/api/export")
def export(body: dict = Body(...)):
    c = charts.build(body["id"], _filters(body.get("filters")), body.get("params") or {})
    fmt = body.get("format", "csv")
    if not c.available:
        raise HTTPException(409, c.reason)
    if fmt == "csv":
        return Response(X.csv_bytes(c.data), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{c.name}.csv"'})
    if fmt == "html":
        return Response(X.html_bytes(c), media_type="text/html", headers={"Content-Disposition": f'attachment; filename="{c.name}.html"'})
    if fmt == "png":
        png, how = X.png_bytes(c)
        if png is None:
            raise HTTPException(409, "no server-side PNG for this chart: use the chart toolbar camera icon")
        return Response(png, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{c.name}.png"', "X-Png-Source": how})
    raise HTTPException(400, "format must be csv, html or png")


@app.get("/api/tournaments")
def tournament_list():
    return {"editions": tournaments.catalogue() + finalissima.catalogue_entries(), "wc2030": {"seasonId": "WC-2030", "slug": "wc-2030", "themeKey": "wc-2030", "status": "coming_soon", "edition": "2030 FIFA World Cup"}}


@app.get("/api/tournament/{season_id}")
def tournament_page(season_id: str):
    if season_id.upper().startswith("FIN-"):
        e = finalissima.edition(season_id)
        if e is None:
            raise KeyError(season_id)
        return {"meta": {k: v for k, v in e.items() if k in finalissima.catalogue_entries()[0]}, "finalissima": True}
    return tournaments.edition(season_id.upper())


@app.get("/api/finalissima")
def finalissima_editions():
    """CONMEBOL-UEFA Cup of Champions (2022 played, 2026 cancelled): curated, sourced, separate from the four-competition warehouse."""
    return {"editions": list(finalissima.EDITIONS.values())}


@app.get("/api/wc2030")
def world_cup_2030():
    return {"facts": wc2030.FACTS, "sources": wc2030.SOURCES}


@app.get("/api/players/search")
def player_search(q: str = Query(..., min_length=2), limit: int = 40):
    return table(Q.player_search(q, limit))


@app.get("/api/matches/{match_key}")
def match_detail(match_key: int):
    row = Q.match_row(match_key)
    if row.empty:
        raise KeyError(match_key)
    return {"match": records(row)[0], "timeline": table(Q.match_timeline(match_key)), "teamStats": table(Q.match_team_stats(match_key)), "lineups": table(Q.match_lineups(match_key))}


@app.post("/api/ml/predict")
def predict(body: dict = Body(...)):
    from ..ml import outcome
    return _jsonify(outcome.predict_matchup(body["a"], body["b"], body["as_of"], competition=body.get("competition", "WC"), stage_name=body.get("stage", "Group stage")))


@app.post("/api/refresh")
def refresh():
    store.refresh()
    charts._eng.cache_clear()
    return {"ok": True}


@app.post("/api/filtered")
def filtered(body: dict = Body(...)):
    """CSV of the filtered matches / player-tournament rows (the Streamlit sidebar download buttons)."""
    from ..viz.filters import apply_matches
    f = _filters(body.get("filters"))
    if body.get("kind") == "players":
        ps = charts.Ctx(f, {}).ps
        cols = ["full_name", "nationality", "team_name", "season_id", "appearances", "starts", "minutes_played", "goals", "assists", "goals_per_90", "primary_position", "age"]
        df = ps[[c for c in cols if c in ps.columns]]
    else:
        df = apply_matches(store.matches_played(), f)
    return Response(X.csv_bytes(df), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="filtered.csv"'})


@app.post("/api/lab/lists")
def lab_lists(body: dict = Body(...)):
    """Option lists for the lab pickers under the current shared filters: team names, player pool, radar players, shot-map teams, matches."""
    from ..viz.filters import apply_matches, apply_team_matches
    f = _filters(body.get("filters"))
    x = charts.Ctx(f, {})
    out: dict = {}
    names = sorted(x.tm.team_name.unique())
    out["teams"] = names
    out["sample"] = {"played": int(len(x.mf)), "total": int(len(store.matches_played())), "playerRows": int(len(x.ps)), "players": int(x.ps.player_key.nunique())}
    term = (body.get("term") or "").strip()
    ps = x.ps
    pool = ps[ps.full_name.str.contains(term, case=False, na=False)] if len(term) >= 2 else ps
    out["players"] = list(pool.groupby("full_name").goals.sum().sort_values(ascending=False).head(300 if len(term) >= 2 else 60).index)
    out["radarPlayers"] = sorted(store.player_stats().full_name.unique())
    if body.get("matches"):
        opts = x.maf.sort_values("match_date", ascending=False).head(400)
        out["matches"] = [{"key": int(r.match_key), "label": f"{pd.Timestamp(r.match_date):%Y-%m-%d} · {r.home_team_name} {'' if pd.isna(r.home_score) else int(r.home_score)}–{'' if pd.isna(r.away_score) else int(r.away_score)} {r.away_team_name} · {r.stage_name} ({r.season_id})" + ("  · COMING SOON" if not r.is_played else ""),
                           "played": bool(r.is_played), "home": r.home_team_name, "away": r.away_team_name, "fixtureDetail": None if r.is_played else r.fixture_detail, "season": r.season_id} for r in opts.itertuples()]
    if body.get("shotSeason"):
        mp = store.matches_played()
        s = mp[mp.season_id == body["shotSeason"]]
        out["shotTeams"] = sorted(set(s.home_team_name) | set(s.away_team_name))
    out["editions"] = list(x.tr.season_id) if len(x.tr) else []
    return _jsonify(out)


@app.get("/api/lab/shap-features")
def shap_features():
    sv = store.shap_values()
    return list(sv[1].columns) if sv is not None else []


@app.get("/api/lab/engineering")
def lab_engineering():
    d = charts._eng()
    failed = d["log"][d["log"].status == "failed"]
    from ..viz import engineering as VE
    return _jsonify({"rawFiles": VE.raw_files(), "failed": failed[["run_id", "step", "attempt", "started_at", "detail"]],
                     "playedMatches": int((d["m"].match_status == "completed").sum()), "comingSoon": int((d["m"].match_status != "completed").sum())})


@app.get("/api/ml/meta")
def ml_meta_info():
    return _jsonify({"meta": Q.ml_meta()})


_POS = {"Goalkeeper": "GK", "Defender": "DF", "Center Back": "DF", "Left Center Back": "DF", "Right Center Back": "DF", "Left Back": "DF", "Right Back": "DF", "Left Wing Back": "DF", "Right Wing Back": "DF",
        "Midfielder": "MF", "Center Midfield": "MF", "Defensive Midfield": "MF", "Attacking Midfield": "MF", "Left Midfield": "MF", "Right Midfield": "MF", "Left Center Midfield": "MF", "Right Center Midfield": "MF",
        "Forward": "FW", "Center Forward": "FW", "Left Wing": "FW", "Right Wing": "FW", "Striker": "FW", "Second Striker": "FW"}


def _lineups(match_key: int) -> pd.DataFrame:
    df = Q.q("""select t.team_name, coalesce(p.full_name, a.player_name_raw) player, a.jersey_number, a.is_starter, a.minutes_played, p.primary_position
                from wh.fact_player_appearances a join wh.dim_team t using (team_key) left join wh.dim_player p using (player_key)
                where a.match_key = %s order by t.team_name, a.is_starter desc nulls last, a.jersey_number""", (int(match_key),))
    df["line"] = df.primary_position.map(_POS)               # unknown positions stay empty: never guessed
    return df


@app.get("/api/match-center/{match_key}")
def match_center(match_key: int):
    """Everything the Match Center shows, from existing warehouse data only. Sections without data are returned empty so the UI can hide them."""
    row = Q.match_row(match_key)
    if row.empty:
        raise KeyError(match_key)
    m = records(row)[0]
    tl, st, lu = Q.match_timeline(match_key), Q.match_team_stats(match_key), _lineups(match_key)
    h2h = Q.head_to_head_table(m["home_team_name"], m["away_team_name"])
    home = m["home_team_name"]
    tl = tl.copy()
    # the same goal can come from two sources (e.g. openfootball and Wikipedia): keep one per scorer and minute
    tl = tl[~(tl.kind.isin(["Goal", "Own goal"]) & tl.duplicated(["kind", "player", "minute", "minute_added"], keep="first"))]
    tl["side"] = tl.team_name.map(lambda t: "home" if t == home else "away")
    is_og = tl.kind.eq("Own goal")
    # StatsBomb stores an own goal under the team of the player who scored it; martj42/fjelstul store it under the team that benefits (verified against every recorded score)
    flip = is_og & tl.provider.eq("statsbomb")
    tl["scoring_side"] = [("away" if sd == "home" else "home") if f else sd for sd, f in zip(tl.side, flip)]
    # assists from every source that records them: StatsBomb pass-to-goal link (related player) or the martj42 assist column
    ass = Q.q("""select e.minute, e.minute_added, coalesce(p.full_name, e.player_name_raw) as player, coalesce(rp.full_name, e.related_player_name_raw, e.assist_name_raw) as assist
                 from wh.fact_match_events e left join wh.dim_player p on p.player_key = e.player_key left join wh.dim_player rp on rp.player_key = e.related_player_key
                 where e.match_key = %s and e.is_goal and not coalesce(e.is_own_goal, false)""", (int(match_key),))
    amap = {(float(r.minute), 0 if pd.isna(r.minute_added) else float(r.minute_added), r.player): r.assist for r in ass.itertuples() if isinstance(r.assist, str)}
    tl["assist"] = [amap.get((float(r.minute), 0 if pd.isna(r.minute_added) else float(r.minute_added), r.player)) if r.kind == "Goal" else None for r in tl.itertuples()]
    goals = tl[tl.kind.isin(["Goal", "Own goal"])]
    mg = Q.q("""select mm.side, mm.manager_name, mm.source, mm.level from wh.fact_match_managers mm where mm.match_key = %s""", (int(match_key),))
    managers = {r.side: dict(name=r.manager_name, source=r.source, level=r.level) for r in mg.itertuples()}
    total = None if not m["is_played"] or m.get("home_score") is None else int(m["home_score"] + m["away_score"])
    complete = total is not None and len(goals) == total
    return {"match": m, "timeline": table(tl), "teamStats": table(st), "lineups": table(lu), "headToHead": table(h2h),
            "goalsComplete": complete, "managers": managers, "assistsRecorded": bool(tl.assist.notna().any()), "hasCommentary": False}                           # no commentary source exists in the warehouse


@app.post("/api/fixtures")
def fixtures(body: dict = Body(...)):
    """Match list for the fixtures page (played matches AND 'Coming soon' fixtures), with server-side filters."""
    m = store.matches_all().copy()
    f = body.get("filters") or {}
    if f.get("competitions"):
        m = m[m.competition_id.isin(f["competitions"])]
    if f.get("seasons"):
        m = m[m.season_id.isin(f["seasons"])]
    if f.get("stages"):
        m = m[m.stage_name.isin(f["stages"])]
    if f.get("date_from"):
        m = m[pd.to_datetime(m.match_date) >= pd.Timestamp(f["date_from"])]
    if f.get("date_to"):
        m = m[pd.to_datetime(m.match_date) <= pd.Timestamp(f["date_to"])]
    q = (body.get("q") or "").strip().lower()
    if q:
        m = m[m.home_team_name.fillna("").str.lower().str.contains(q, regex=False) | m.away_team_name.fillna("").str.lower().str.contains(q, regex=False)]
    status = body.get("status", "all")
    if status == "played":
        m = m[m.is_played]
    elif status == "upcoming":
        m = m[~m.is_played]
    elif status == "extra_time":
        m = m[m.went_beyond_90.fillna(False) & m.is_played]
    elif status == "penalties":
        m = m[m.had_shootout.fillna(False) & m.is_played]
    m = m.sort_values(["match_date", "match_key"], ascending=body.get("order", "desc") == "asc")
    total, off, lim = int(len(m)), int(body.get("offset", 0)), min(int(body.get("limit", 120)), 400)
    cols = ["match_key", "match_date", "competition_id", "season_id", "stage_name", "group_name", "home_team_name", "away_team_name", "home_score", "away_score", "home_pen", "away_pen", "went_beyond_90", "had_shootout",
            "status_label", "is_played", "venue_name", "venue_city", "fixture_detail", "matchday"]
    return {"total": total, "rows": records(m.iloc[off:off + lim][[c for c in cols if c in m.columns]], limit=lim)}


@app.get("/api/standings/{season_id}")
def standings(season_id: str):
    s = store.standings()
    s = s[s.season_id == season_id.upper()].sort_values(["group_name", "group_position"])
    return {"table": table(s), "basis": None if s.empty else str(s.basis.iloc[0])}


@app.get("/api/teams/all")
def all_teams():
    """Every team name in the data (for the flag-coverage test and pickers)."""
    m = store.matches_all()
    return sorted(set(m.home_team_name.dropna()) | set(m.away_team_name.dropna()))


# --- serve the built React app (single-command deployment); API routes above take precedence
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    app.mount("/logos", StaticFiles(directory=DIST / "logos"), name="logos")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
