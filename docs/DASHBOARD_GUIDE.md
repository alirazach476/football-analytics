# Dashboard guide

Start: `docker compose up -d`, run the pipeline once, then
```bash
set PYTHONPATH=src
streamlit run src/fbplatform/dashboard/app.py
```
Open http://localhost:8501. Wide layout, collapsible sidebar with filters, Plotly charts (hover, zoom, download), responsive columns. If the warehouse is down every page says so and stops.

## Pages

| # | Page | Shows | Filters |
|---|---|---|---|
| 1 | **Overview** | competitions, editions, matches played, teams, players, goals, events, venues, data-quality score, coverage heat-map by edition, **Coming soon** fixtures | coverage measure |
| 2 | **Competition analysis** | edition comparison (per-match rates), outcome distribution, tournament records, champions, top scorers, goals by minute band | competition |
| 3 | **Team analytics** | W-D-L, win %, goal difference, clean sheets, performance by edition, results history, scoring trend, team comparison, head-to-head, upcoming fixtures | team, comparison team |
| 4 | **Player analytics** | profile (goals, assists where recorded, appearances, known minutes, awards), top lists, two-player comparison | name search, ranking measure |
| 5 | **Match analytics** | match search, scoreboard (with shoot-out), event timeline (goals/cards/substitutions), team statistics, line-ups, head-to-head, goal timing; scheduled fixtures show **Coming soon** with their known details | edition, team, include-upcoming |
| 6 | **Machine learning** | model comparison with intervals, confusion matrices, out-of-sample predictions vs actual results, goal models and diagnostics, over/under experiment, permutation/SHAP/partial dependence, clustering, a **matchup predictor** | model, feature, teams/date/stage |
| 7 | **Data engineering** | pipeline run history, ingestion status, data-quality checks, coverage and missing data, duplicate/entity-resolution checks, database table sizes, freshness | failed-only toggle |

## Visualization lab

A second sidebar group, **Visualization lab**, adds seven chart-heavy pages (competitions, teams, players, matches, statistics, machine learning, data engineering) with shared filters, cross-filtering and downloads. See `docs/VISUALIZATION_GUIDE.md`.

## How to read it correctly

* **Coming soon** = scheduled and not played: no score exists, none is shown or modelled. Teams may be placeholders (e.g. "A1") until decided.
* **Prediction** = model output made without the result (always labelled, with a warning banner on the ML page). The matchup predictor uses only matches before the chosen date.
* **Data quality score** = share of automated checks that pass; it is *not* a completeness measure — use the coverage heat-map for that.
* **Player numbers** cover only the collected competitions (not careers). Goals are goals linked to a player id (Nations League scorers are not linked); assists exist only where the sources record them; minutes for Wikipedia-based editions are approximate.
* **"Listed first"** is not "home": most tournament matches are on neutral ground.
* Blank heat-map cells mean "nothing to measure yet" (e.g. the upcoming edition), not zero.

## Data access and caching

Pages call `fbplatform.dashboard.queries` (pure SQL functions over the warehouse, Gold marts and monitoring schema, or the saved files in `reports/`). Results are cached for 5 minutes (`st.cache_data`); restart or press `C` in the app to clear. The ML page reads saved reports and models; it never retrains.

## Extending

Add a query function to `queries.py` (and a test in `tests/test_dashboard.py`), then a view in `dashboard/views/` and register it in `app.py`. `tests/test_dashboard.py` renders every view headless (`streamlit.testing.v1.AppTest`) and fails on any exception.
