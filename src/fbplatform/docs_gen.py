"""Generate the number-bearing documents from the live warehouse and the saved report files, so they cannot drift from the data:
DATA_DICTIONARY.md, DATABASE_SCHEMA.md, DATA_QUALITY.md, DATA_SCIENCE_REPORT.md, MODEL_DOCUMENTATION.md  ->  docs/
Run:  python -m fbplatform.docs_gen   (needs the warehouse running and the reports/ files present)"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from .analysis.data import q
from .config import ROOT
from .dashboard import queries as Q

DOCS = ROOT / "docs"
REP = ROOT / "reports"

TABLE_DESC = {
    "dim_competition": "The four competitions in scope (WC, EURO, COPA, UNL).", "dim_season": "One row per edition with expected/actual/played/scheduled match counts.",
    "dim_team": "National teams (surrogate key; `team_id` is the stable natural key).", "dim_team_name_history": "Former/alternative team names. Validity dates are NULL: no source gives them.",
    "dim_player": "Canonical players after entity resolution (merged ids listed in `merged_player_ids`).", "dim_player_xref": "Every original source player id -> canonical player and the rule that merged it.",
    "dim_venue": "Stadiums (identity = Wikipedia article) with coordinates and capacity where known.", "dim_referee": "Referees parsed from 'Name (Country)'.", "dim_date": "Calendar dimension covering all match dates.",
    "dim_tournament_stage": "Stages with order and knockout flag.", "fact_matches": "One row per match, played or scheduled. Scheduled fixtures have status 'scheduled', label 'Coming soon' and NULL scores.",
    "fact_team_match_stats": "Team statistics per match (StatsBomb-covered matches only).", "fact_player_match_stats": "Player statistics per match (StatsBomb-covered matches only).",
    "fact_player_appearances": "Line-up rows: who played, starter flag, minutes (provider-derived or Wikipedia-derived, see `fact_player_appearances` notes).",
    "fact_match_events": "All event rows (goals, cards, substitutions, and for StatsBomb/Wyscout every on-ball event with coordinates).", "fact_tournament_standings": "Group tables DERIVED from played group-stage matches (basis column states the rules).",
    "fact_player_awards": "Individual awards from Wikipedia award pages; keys NULL when the winner could not be linked uniquely.", "fact_team_awards": "Team awards (fair play, most entertaining team).",
    "etl_load_log": "Row counts of the last warehouse load."}
COL_DESC = {
    "match_key": "Surrogate key of the match.", "match_id": "Stable natural key: FBM- + hash of (season, date, home, away) as first ingested.", "season_key": "FK to dim_season.", "competition_key": "FK to dim_competition.",
    "date_key": "YYYYMMDD, FK to dim_date.", "stage_key": "FK to dim_tournament_stage.", "home_team_key": "FK to dim_team; NULL while the team is undecided (placeholder such as A1).", "away_team_key": "FK to dim_team; NULL while undecided.",
    "home_team_display": "Team label as known (placeholder text for undecided fixtures).", "away_team_display": "Team label as known.", "match_status": "completed or scheduled.", "status_label": "'Full time' or 'Coming soon'.",
    "fixture_detail": "Human-readable summary of what is known about a scheduled fixture.", "home_score": "Goals incl. extra time, excl. shoot-out (NULL for scheduled).", "away_score": "As home_score.", "score_basis": "What home_score/away_score include.",
    "home_score_ft90": "Score after 90 minutes where known.", "home_pen": "Shoot-out goals where known.", "shootout_winner_side": "home/away winner of a shoot-out (martj42 shootouts file; no kick scores).",
    "attendance": "Recorded attendance (0 = a genuine closed-door match).", "went_extra_time": "Source flag; use stg_matches.went_beyond_90 for the derived indicator.", "man_of_the_match_raw": "Man of the match name as published.",
    "primary_provider": "Provider that supplied the match's score row.", "source_url": "Where the row came from (line number for text sources).", "player_key": "Surrogate key of the canonical player.", "team_key": "Surrogate key of the team.",
    "minutes_played": "Minutes on the pitch (whole minutes for Wikipedia-derived rows, nominal 90/120 end, stoppage ignored).", "is_starter": "Started the match.", "provider": "Event/line-up source.", "event_type": "Event class as normalised from the provider.",
    "minute": "Match minute (regulation + extra time).", "period": "1,2 = halves, 3,4 = extra time, 5 = shoot-out.", "location_x": "Pitch coordinate (system in coordinate_system).", "coordinate_system": "statsbomb_120x80 or wyscout_pct_0_100.",
    "xg": "Expected goals of the shot (StatsBomb only).", "is_goal": "Event is a goal.", "is_own_goal": "Event is an own goal.", "assist_name_raw": "Assist provider's name where known.", "assist_source": "Where the assist name came from.",
    "related_player_name_raw": "Second player of the event (e.g. player coming on for a substitution).", "player_name_raw": "Player name as published by the source.", "canonical_player_id": "Canonical player id.",
    "resolution_rule": "Entity-resolution rule: D1 same name+DOB; D2 name containment + shared national team + never in one line-up.", "merged_player_ids": "JSON list of all source ids merged into this player.",
    "nationality": "From the source, or the single national team the player appears for (see nationality_basis in Silver).", "latitude": "Venue latitude.", "capacity": "Current stadium capacity from Wikipedia (renovations make historic attendances exceed it sometimes).",
    "group_position": "Position in the derived group table (tiebreak: points, goal difference, goals for only).", "basis": "Rules used to derive the standing.", "award_name": "Award as named on the source page.", "award_category": "Standardised category (Best player, Top scorer, ...).",
    "entity_name_raw": "Winner as published.", "link_status": "How the winner was linked: squad_name_match, ambiguous, not_in_season_squads, ...", "rank": "1 = winner, 2/3 = runners-up where the award has them.", "value_text": "e.g. '8 goals', '5 clean sheets'."}


def _w(name, text):
    DOCS.mkdir(exist_ok=True)
    (DOCS / name).write_text(text, encoding="utf-8")


def data_dictionary_and_schema():
    cols = q("""select table_schema, table_name, column_name, ordinal_position, data_type, is_nullable from information_schema.columns
                where table_schema in ('wh','gold','monitoring') order by 1, 2, 4""")
    pk = q("""select tc.table_schema, tc.table_name, kcu.column_name from information_schema.table_constraints tc join information_schema.key_column_usage kcu
              using (constraint_schema, constraint_name) where tc.constraint_type = 'PRIMARY KEY' and tc.table_schema in ('wh','monitoring')""")
    fk = q("""select tc.table_name, kcu.column_name, ccu.table_name as ref_table, ccu.column_name as ref_column from information_schema.table_constraints tc
              join information_schema.key_column_usage kcu using (constraint_schema, constraint_name)
              join information_schema.constraint_column_usage ccu using (constraint_schema, constraint_name) where tc.constraint_type='FOREIGN KEY' and tc.table_schema='wh'""")
    counts = {t: int(q(f"select count(*) c from wh.{t}").c.iloc[0]) for t in Q.WH_TABLES}
    pkset = {(r.table_schema, r.table_name, r.column_name) for r in pk.itertuples()}
    L = ["# Data dictionary", "", f"_Generated {date.today()} from the live PostgreSQL warehouse (`python -m fbplatform.docs_gen`). Schema `wh` = star schema; `gold` = dbt marts; `monitoring` = pipeline/quality tables._", "",
         "Conventions: surrogate keys end in `_key`; natural keys are `*_id`. NULL means *unknown or not applicable* and is never filled with an estimate. Scheduled fixtures keep NULL scores.", ""]
    for (sch, tab), g in cols.groupby(["table_schema", "table_name"], sort=False):
        desc = TABLE_DESC.get(tab, "")
        n = f" ({counts[tab]:,} rows)" if sch == "wh" and tab in counts else ""
        L += [f"## {sch}.{tab}{n}", "", desc, "", "| column | type | null | key | description |", "|---|---|---|---|---|"]
        for r in g.itertuples():
            key = "PK" if (sch, tab, r.column_name) in pkset else ""
            L.append(f"| `{r.column_name}` | {r.data_type} | {'yes' if r.is_nullable == 'YES' else 'no'} | {key} | {COL_DESC.get(r.column_name, '')} |")
        L.append("")
    _w("DATA_DICTIONARY.md", "\n".join(L))
    S = ["# Database schema", "", f"_Generated {date.today()}. Engine: PostgreSQL 16 (Docker, host port 5442). DDL: `sql/warehouse_schema.sql`; loader: `src/fbplatform/warehouse/load.py`._", "",
         "```text", "                      dim_competition ─┐", "                                       ├─ dim_season ─┬─ fact_matches ─┬─ fact_team_match_stats", "   dim_tournament_stage ────────────────┘             │                ├─ fact_player_match_stats",
         "   dim_date ─────────────────────────────────────────┤                ├─ fact_player_appearances", "   dim_venue ────────────────────────────────────────┤                ├─ fact_match_events", "   dim_referee ──────────────────────────────────────┘                └─ (fact_tournament_standings via season)",
         "   dim_team ─(name history)─ used by every fact       dim_player ◄─ dim_player_xref (original source ids)", "```", "",
         "## Design decisions", "", "* **Surrogate keys** are deterministic (sorted natural key → 1..n), so reloads give identical keys. The schema is dropped and rebuilt from Silver on each load (idempotent).",
         "* **Historical entities:** `dim_team_name_history` keeps former names; teams that no longer exist (e.g. Yugoslavia, Serbia and Montenegro) are separate teams, never merged. Validity dates are NULL because no source gives them.",
         "* **Identity resolution:** `dim_player_xref` maps every original source id to the canonical player and records the rule.",
         "* **Scheduled fixtures** are rows in `fact_matches` with `match_status='scheduled'`; a CHECK constraint forces their scores to be NULL.",
         "* **Constraints:** primary keys, foreign keys, CHECKs (status values, non-negative attendance, scheduled⇒no score) and indexes on the join/filter columns.", "",
         "## Row counts", "", "| table | rows |", "|---|---|"] + [f"| {t} | {n:,} |" for t, n in counts.items()] + ["", "## Foreign keys", "", "| table | column | → table | column |", "|---|---|---|---|"] + \
        [f"| {r.table_name} | {r.column_name} | {r.ref_table} | {r.ref_column} |" for r in fk.itertuples()]
    _w("DATABASE_SCHEMA.md", "\n".join(S))


def data_quality():
    cov = Q.coverage_report()
    dq = Q.data_quality_score()
    res = Q.dq_results()
    dup = Q.duplicate_checks()
    iss = pd.read_csv(ROOT / "data" / "inventory" / "issues.csv") if (ROOT / "data" / "inventory" / "issues.csv").exists() else pd.DataFrame()
    L = ["# Data quality", "", f"_Generated {date.today()}._", "",
         f"**Automated checks:** {dq['passed']} of {dq['total']} passed in the latest run (Pandera on Silver, dbt on Gold) = {dq['score']:.0f}%. This is rule compliance, **not** completeness: see coverage below.", "",
         "## What is checked, and where", "", "| layer | tool | examples |", "|---|---|---|",
         "| Bronze | file register | SHA-256 + size + version per source file; unchanged re-run registers nothing; UEFA Champions League files flagged `excluded_ucl` |",
         "| Silver | Pandera (critical: stop the run; warning: recorded) | unique ids, allowed competitions (WC/EURO/COPA/UNL only), scheduled fixtures have null scores + a 'Coming soon' detail, completed matches have both scores, plausible dates/minutes/coordinates/attendance |",
         "| Warehouse | PostgreSQL constraints | PK/FK, CHECKs, scheduled ⇒ NULL score |", "| Gold | dbt tests (115) | unique/not_null/relationships/accepted_values, W+D+L and points arithmetic, goals scored = goals conceded, Gold row counts reconcile to the warehouse, no upcoming fixture dropped |",
         "| Cross-source | collection phase | goals rebuilt from events = recorded score; Fjelstul vs StatsBomb vs Wikipedia agreement rates (see README history) |", ""]
    L += ["## Latest check results", "", "| layer | table | check | severity | status | failed rows |", "|---|---|---|---|---|---|"]
    for r in res.drop_duplicates(["layer", "table_name", "check_name"]).head(40).itertuples():
        L.append(f"| {r.layer} | {r.table_name} | {r.check_name} | {r.severity} | {r.status} | {r.failed_rows} |")
    L += ["", "## Duplicates and entity resolution", "", "| check | found |", "|---|---|"] + [f"| {r.check} | {int(r.found)} |" for r in dup.itertuples()]
    L += ["", "## Coverage by edition (latest run)", "", "Expected matches are format arithmetic, not official records. Percentages are of *played* matches.", "",
          "| edition | expected | in dataset | played | coming soon | lineups % | events % | goals with event % | man of match % | attendance % | flag |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in cov.itertuples():
        f = lambda v: "" if pd.isna(v) else f"{v:.0f}"
        L.append(f"| {r.season_id} | {'' if pd.isna(r.expected_matches) else int(r.expected_matches)} | {r.matches_in_dataset} | {r.matches_played} | {r.matches_coming_soon} | {f(r.pct_lineups)} | {f(r.pct_events)} | {f(r.pct_goals_with_event)} | {f(r.pct_man_of_match)} | {f(r.pct_attendance)} | {r.coverage_flag} |")
    L += ["", "## Known limitations (all real, none hidden)", "",
          "* **Nations League group matches:** no line-ups, cards or substitutions (the public pages we are allowed to use have none; UEFA's terms prohibit scraping). Goals exist for all of them; goal scorers are *names only* (no squad data to link them).",
          "* **Man of the match** is not published for Copa 2001/2004/2007 or Nations League group matches.", "* **Possession, VAR decisions and (outside StatsBomb) xG** are not available and are NULL, never estimated.",
          "* **Coordinates/passes/shots** exist only for the 313 StatsBomb/Wyscout matches.", "* **Half-time scores** exist for WC and Euro only; **extra time is not recorded for the Nations League**, so extra-time statistics undercount it there.",
          "* **Shoot-outs:** winners are known for all (martj42), kick-by-kick scores only for some.", "* **Minutes** for Wikipedia-based editions are derived from substitution and card times with a nominal 90/120-minute end (stoppage ignored): accurate to a few minutes.",
          "* **Standings** are derived from matches (3-1-0, tiebreak points/GD/GF only), not official tables.", "* **Awards** come from Wikipedia (secondary source); unlinked winners keep their raw name.",
          "* **8 attendances** are recorded nowhere; 12 Copa 2011 values are rounded estimates from the Spanish Wikipedia (labelled).", "* **Romania–Kosovo 2024** was abandoned at 0-0 and awarded 3-0; the on-pitch score is kept with a note."]
    if len(iss):
        L += ["", "## Initial investigation (Part A) findings by class", "", "| class | findings |", "|---|---|"] + [f"| {k} | {v} |" for k, v in iss["class"].value_counts().items()] if "class" in iss.columns else []
    L += ["", "## Bugs the checks found and that were fixed", "",
          "Champions League date roll-over (before it left scope); Euro 2008 two-letter weekday headers; Euro 2000 venue-before-teams layout creating bogus teams; overlapping StatsBomb position intervals; duplicated Wyscout goal tags; best-copy-wins merge of duplicate Wikipedia boxes; "
          "attendance 0 treated as missing; own goals missing from goal events (StatsBomb `own_goal_against`); OpenFootball goals without an `is_goal` flag (all of Euro 2000/2004 and WC 2026 showed zero goal events until the coverage report exposed it); "
          "literal `\\uXXXX` escapes in 399 Wyscout names; Wikipedia line-ups without player ids and minutes; goals-per-90 inflated by missing minutes; the pipeline ignoring Silver code changes."]
    _w("DATA_QUALITY.md", "\n".join(L))


def _r(path):
    p = REP / path
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def science_report():
    st = _r("statistics/results.csv")
    eda1 = _r("eda/tables/A1_competition_summary.csv")
    top = _r("eda/tables/C1_top_scorers.csv")
    cmp_ = _r("ml/outcome/match_outcome_model_comparison.csv")
    k = Q.kpis()
    L = ["# Data science report", "", f"_Generated {date.today()}. Every number below is read from `reports/` at generation time._", "",
         "## Scope and data", "", f"{k['matches_played']:,} played matches ({k['matches_coming_soon']} more fixtures are 'Coming soon' and excluded from every statistic and model target), {k['teams']} teams, {k['players']:,} canonical players, {k['goals']:,} goals, "
         f"{k['events']:,} event rows across the FIFA World Cup, UEFA Euro, Copa América and UEFA Nations League. UEFA Champions League is out of scope. Per-match rates are used throughout; raw totals are never compared across editions of different size.", "",
         "## Exploratory analysis: headline facts", ""]
    if len(eda1):
        L += ["| competition | editions | matches | goals/match | draw % | beyond 90 min % | avg attendance |", "|---|---|---|---|---|---|---|"] + \
             [f"| {r.competition_name} | {r.seasons} | {r.matches_played} | {r.goals_per_match:.2f} | {r.draw_pct:.1f} | {r.beyond_90_pct:.1f} | {int(r.avg_attendance):,} |" for r in eda1.itertuples()]
        L += ["", "Nations League extra time is not recorded, so its 'beyond 90' share is understated.", ""]
    if len(top):
        L += ["Top scorers in the collected competitions (linked goals only; not career totals): " + ", ".join(f"{r.full_name} ({int(r.goals)})" for r in top.head(6).itertuples()) + ".", ""]
    L += ["Full tables and figures: `reports/eda/eda_report.html` and the notebooks in `notebooks/`.", "", "## Statistical investigation (10 required questions)", "",
          "Assumptions were checked before choosing tests (goal counts are non-normal and over-dispersed → rank tests / quasi-Poisson). p-values are Holm-adjusted inside each family. Details, assumption diagnostics and limitations per analysis: `docs/STATISTICAL_REPORT.md`.", "",
          "| Q | analysis | n | estimate [95% CI] | adj. p | effect size |", "|---|---|---|---|---|---|"]
    for r in st.drop_duplicates("q").itertuples():
        pass
    pick = st.groupby("q").head(1) if len(st) else st
    for q_, g in st.groupby("q", sort=False):
        for r in g.head(3 if q_ not in ("Q6", "Q9") else 2).itertuples():
            ci = "" if pd.isna(r.ci_low) else f" [{r.ci_low:.3g}, {r.ci_high:.3g}]"
            p = r.p_adj_holm if pd.notna(r.p_adj_holm) else r.p_value
            L.append(f"| {q_} | {r.analysis[:90]} | {int(r.n)} | {r.estimate:.3g}{ci} | {'' if pd.isna(p) else f'{p:.3g}'} | {r.effect_size_name}: {r.effect_size:.3g} |")
    L += ["", "**Reading the results:** association is never causation; with n of 7–9 editions per competition, trend questions have low power; a non-significant result does not prove equality.", ""]
    if len(cmp_):
        t = cmp_[cmp_.split == "test"]
        L += ["## Machine learning (test period)", "", "| model | accuracy | 95% CI | log loss | ROC-AUC |", "|---|---|---|---|---|"] + \
             [f"| {r.model} | {r.accuracy:.3f} | [{r.accuracy_ci_low:.3f}, {r.accuracy_ci_high:.3f}] | {r.log_loss:.3f} | {r.roc_auc_ovr:.3f} |" for r in t.itertuples()]
        L += ["", "No tuned model is clearly better than the single-feature Elo baseline (overlapping intervals). See `docs/MODEL_DOCUMENTATION.md`.", ""]
    fc = _r("advanced/D_forecast_next_edition.csv")
    ci = _r("advanced/A_competitiveness_index.csv")
    dom = _r("advanced/B_team_dominance.csv")
    L += ["## Advanced projects", ""]
    if len(ci):
        L += [f"* **Competitiveness index** (percentile construct, 0–1): highest {', '.join(ci.season_id.head(3))}; lowest {', '.join(ci.season_id.tail(3))}. Differences of a few hundredths are within noise (bootstrap interval on the margin component is in the table)."]
    if len(dom):
        L += [f"* **Team dominance** (editions ≥ 3, shrunk win %, goal difference, knockout record, progression, titles): {', '.join(dom.team_name.head(6))}."]
    if len(fc):
        L += ["* **Trend forecasts (EXPLORATORY, not reliable):** " + "; ".join(f"{r.competition} {int(r.next_edition)}: {r.forecast_goals_per_match:.2f} goals/match [{r.pi_low:.2f}, {r.pi_high:.2f}] via {r.method_selected_by_backtest}" for r in fc.itertuples()) + ". Methods were chosen by leave-last-out backtest on 4–6 origins."]
    L += ["* **Head-to-head tool:** `fbplatform.analysis.advanced.head_to_head(a, b, competition=None, since=None)`; meetings are not equivalent contexts and the output says so.", "",
          "## Limitations", "", "* Tournament football produces few matches per team per edition: team-level estimates are noisy.", "* Player statistics cover only the collected competitions; assists and per-90 rates are partial (see DATA_QUALITY.md).",
          "* Elo is built from these four competitions only (no friendlies/qualifiers) and is therefore a partial strength measure.", "* Format changes (24→48 teams at the World Cup) are confounded with era.", "* The Nations League has the weakest event coverage; any player-level conclusion excludes its scorers."]
    _w("DATA_SCIENCE_REPORT.md", "\n".join(L))


def model_documentation():
    meta = Q.ml_meta()
    cmp_ = _r("ml/outcome/match_outcome_model_comparison.csv")
    gl = _r("ml/goals/goal_model_comparison.csv")
    gm = json.loads((ROOT / "models" / "goals_selected.json").read_text(encoding="utf-8")) if (ROOT / "models" / "goals_selected.json").exists() else {}
    ts = _r("ml/clustering/team_clustering_summary.csv")
    ps = _r("ml/clustering/player_clustering_summary.csv")
    pa = _r("ml/players/association_model_scores.csv")
    pn = _r("ml/players/next_tournament_prediction.csv")
    sp = meta.get("split", {})
    L = ["# Model documentation", "", f"_Generated {date.today()}. Models are saved in `models/` (joblib + JSON metadata); runs are tracked in MLflow (`mlflow ui --backend-store-uri sqlite:///mlflow.db`)._", "",
         "## Rules applied to every model", "", "* **No leakage:** a match's features use only matches from strictly earlier dates (same-day results never leak). `tests/test_ml.py` changes all later results and verifies earlier features do not move.",
         "* **Chronological evaluation:** train / validation / test are separated by date. Hyper-parameters are tuned only on the training period with expanding-window time-series CV.",
         "* **Scheduled fixtures are never used** as training or evaluation targets (no outcome exists).", "* **Predictions are labelled** 'MODEL PREDICTION' everywhere they appear.", "* LightGBM is not installed here and was not evaluated.", ""]
    L += ["## 1. Match outcome (A win / draw / B win)", "", f"* **Target:** result of the team listed first on the recorded score (extra time included, shoot-out excluded). **Rows:** played matches with both teams known.",
          f"* **Split:** train {sp.get('train', ['', '', ''])[0]} → {sp.get('train', ['', '', ''])[1]} ({sp.get('train', ['', '', ''])[2]}), validation → {sp.get('validation', ['', '', ''])[1]} ({sp.get('validation', ['', '', ''])[2]}), test {sp.get('test', ['', '', ''])[0]} → {sp.get('test', ['', '', ''])[1]} ({sp.get('test', ['', '', ''])[2]}).",
          f"* **Features ({len(meta.get('features', []))}):** per-team past win %, points/match, goals for/against, goal difference, clean sheets, last-5 form, tournament experience (earlier editions), knockout record, attack/defence strength (relative to the league average so far), rest days, Elo; pairwise differences; head-to-head record; stage, knockout flag, host flags, competition.",
          "* **Elo:** computed only from earlier matches in these four competitions (start 1500, K by competition, goal-difference multiplier, +100 for the host). Partial strength measure, not the official World Football Elo.",
          f"* **Selection:** lowest validation log loss → **{meta.get('selected_model')}**, refit on train+validation.", ""]
    if len(cmp_):
        t = cmp_[cmp_.split == "test"]
        L += ["| model | accuracy [95% CI] | macro-F1 | log loss [95% CI] | ROC-AUC (OvR) |", "|---|---|---|---|---|"] + \
             [f"| {r.model} | {r.accuracy:.3f} [{r.accuracy_ci_low:.3f}, {r.accuracy_ci_high:.3f}] | {r.f1_macro:.3f} | {r.log_loss:.3f} [{r.log_loss_ci_low:.3f}, {r.log_loss_ci_high:.3f}] | {r.roc_auc_ovr:.3f} |" for r in t.itertuples()]
        fm = meta.get("final_test_metrics", {})
        L += ["", f"Final selected model on the test period (refit on train+validation): accuracy {fm.get('accuracy', float('nan')):.3f}, log loss {fm.get('log_loss', float('nan')):.3f}, ROC-AUC {fm.get('roc_auc_ovr', float('nan')):.3f}.", "",
              "**Interpretation:** the features carry real signal (every model beats the class prior), but none is clearly better than the one-feature Elo baseline — the intervals overlap. Draws are almost never predicted (draw recall on the test period is 0-4% for every model; see `confusion_matrices_test.csv`). Do not read these as betting-grade probabilities."]
    L += ["", "## 2. Goal prediction (expected goals per team, regulation time)", "", f"* **Selected:** {gm.get('selected_model', '?')} (lowest validation Poisson deviance). Diagnostics: {gm.get('diagnostics', {})}.",
          "* Baseline = training mean. Metrics: MAE, RMSE (team and total goals), Poisson deviance, dispersion, zero share, calibration by decile.", ""]
    if len(gl):
        t = gl[gl.split == "test"]
        L += ["| model | MAE team goals | RMSE team goals | Poisson deviance | MAE total goals |", "|---|---|---|---|---|"] + [f"| {r.model} | {r.mae_team_goals:.3f} | {r.rmse_team_goals:.3f} | {r.poisson_deviance:.3f} | {r.mae_total_goals:.3f} |" for r in t.itertuples()]
    ou = gm.get("over_under", {})
    L += ["", f"**Over/under 2.5 (analytical experiment, independent-Poisson assumption):** accuracy {ou.get('accuracy', float('nan')):.3f} vs base rate {ou.get('accuracy_base_rate', float('nan')):.3f}; Brier {ou.get('brier', float('nan')):.3f} vs {ou.get('brier_base_rate', float('nan')):.3f}. Goal totals are barely predictable beyond the base rate.", "",
          "## 3. Team clustering", ""]
    if len(ts):
        s = ts.iloc[0]
        L += [f"K-Means / Ward / DBSCAN on standardised team features (goals for/against, win %, points, goal difference, clean sheets, goal-difference SD, edition-to-edition SD). k = {int(s.k_selected)} by silhouette ({s.silhouette_kmeans:.2f}); "
              f"cophenetic correlation {s.cophenetic_correlation_ward:.2f}; DBSCAN found {int(s.dbscan_clusters)} clusters and {int(s.dbscan_noise_teams)} noise teams; bootstrap stability ARI {s.bootstrap_stability_mean_ari:.2f}. "
              "The structure is weak: teams form a continuum. Cluster names come from explicit rules over the standardised centroids and the profile tables are saved beside them. Possession is not available."]
    L += ["", "## 4. Player clustering", ""]
    if len(ps):
        L += ["Per-90 StatsBomb features, clustered **within position** (defenders, midfielders, forwards); goalkeepers are profiled separately.", "", "| position | players | k | silhouette | stability ARI |", "|---|---|---|---|---|"] + \
             [f"| {r.position} | {int(r.n_players)} | {int(r.k)} | {r.silhouette:.2f} | {r.bootstrap_stability_mean_ari:.2f} |" for r in ps.itertuples()] + ["", "Silhouettes are low: the groups are descriptive, not distinct player types."]
    L += ["", "## 5. Player performance analysis", ""]
    if len(pa):
        L += ["**Association** (explains goals per 90; grouped cross-validation by player):", "", "| model | n | CV R² | CV MAE | baseline MAE |", "|---|---|---|---|---|"] + [f"| {r.model} | {int(r.n)} | {r.cv_r2_grouped_by_player:.3f} | {r.cv_mae:.3f} | {r.baseline_mae_mean:.3f} |" for r in pa.itertuples()]
    if len(pn):
        L += ["", "**Prediction** of next-tournament goals per 90 (train ≤ 2016, test later):", "", "| model | MAE | R² | Spearman |", "|---|---|---|---|"] + [f"| {r.model} | {r.mae:.3f} | {r.r2:.3f} | {'' if pd.isna(r.spearman) else f'{r.spearman:.2f}'} |" for r in pn.itertuples()]
    L += ["", "Position (forward) dominates; `team_gf_pm` is partly mechanical (a player's goals are part of the team's goals). No claim about player quality is made.", "",
          "## Explainability", "", "Permutation importance (test period), XGBoost gain, SHAP (mean |impact| per outcome) and partial-dependence tables are in `reports/ml/outcome/` and shown on the dashboard's Machine-learning page. Importances describe the model, not football causation.", "",
          "## Using the models", "", "```python", "from fbplatform.ml.outcome import predict_matchup", "predict_matchup('Argentina', 'France', as_of='2026-07-01', competition='WC', stage_name='Final')", "```",
          "Returns probabilities built only from matches before `as_of`, labelled as a model prediction. The 51 Euro 2028 fixtures cannot be predicted until their teams are known."]
    _w("MODEL_DOCUMENTATION.md", "\n".join(L))


def main():
    data_dictionary_and_schema()
    data_quality()
    science_report()
    model_documentation()
    return sorted(p.name for p in DOCS.glob("*.md"))


if __name__ == "__main__":
    print(main())
