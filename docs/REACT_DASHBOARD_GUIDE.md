# React dashboard guide

The Streamlit dashboard (still available) has been rebuilt as a React app, with one themed page per tournament edition.

## Run it
```
docker compose up -d                               # warehouse (port 5442)
set PYTHONPATH=src
python -m uvicorn fbplatform.api.main:app --port 8000
cd frontend && npm install && npm run build        # once; the API then serves frontend/dist at http://localhost:8000
# development with hot reload:  npm run dev   (http://localhost:5173, proxies /api to port 8000)
```
Tests: `python -m pytest tests/test_api.py` and `cd frontend && npm test`.

## Architecture
- **Backend** `src/fbplatform/api/` (FastAPI). It reuses the code that fed Streamlit: Python builds every Plotly figure (`viz/` package, 85 chart ids in `api/charts.py`) and returns it as JSON, so React draws exactly what Streamlit drew and every "Not shown: reason" rule is preserved. Other endpoints: `/api/query` (whitelisted dashboard queries), `/api/tournaments`, `/api/tournament/{season}`, `/api/wc2030`, `/api/lab/*` (pickers), `/api/export` (CSV/HTML/PNG), `/api/filtered`, `/api/ml/predict`.
- **Frontend** `frontend/` (React 18, TypeScript, Vite, Tailwind, TanStack Query, framer-motion, Plotly lazy-loaded).
- **Pages**: Home; competition hubs; one page per edition (`/tournament/<slug>`); `/wc-2030`; 7 Analytics pages and 7 Visualization-lab pages (same content, filters, cross-filtering, table view and downloads as the Streamlit pages).

## Tournament themes (from the logos)
`python tools/prepare_logos.py "<folder with the logo images>"` copies each logo/banner to `frontend/public/logos/` and extracts a colour palette into `frontend/src/data/themes.auto.json`. `frontend/src/theme/editions.ts` holds the curated colour tokens, light/dark mode and decorative pattern for each edition; the page applies them as CSS variables. All Nations League editions share one theme (`unl`) because they share one logo. Logos sit on a light plate so dark logos stay visible on dark themes.

## Rules kept
Men's four competitions only (no Champions League); nothing invented; missing data stays empty; upcoming fixtures say **Coming soon** and are never part of statistics or ML targets; predictions are always labelled.

## FIFA World Cup 2030 page
Built only from the cited sources (listed on the page). Each item is marked confirmed, provisional or undecided: the final team count, venue list, schedule, emblem, mascot, ball and qualification slots are **not** confirmed. It shows no results, standings, awards or predictions.

## Known limits
Nations League editions have no recorded team count/dates in the data (shown as "to be confirmed"/"–"); Nations League scorers are not linked to players, so scorer tables are empty there. Euro 2028 fixtures exist; Copa América 2028 has none yet.

## Match Center, fixtures and flags (broadcast-style redesign)
- **Routes**: `/fixtures` (filter by team, competition, edition, stage, date, status; sort; played or Coming soon) and `/match/:key` (Match Center). Tournament pages gained **Standings** and **Bracket** tabs and a scoreboard-card view of all matches.
- **Match Center** (`pages/MatchCenter.tsx`, `components/match/`): scoreboard (competition logo, flags, score, status, penalties, scorers, venue/referee), then tabs **Overview / Statistics / Lineups / Events / Commentary / Head-to-Head**. A tab appears only if its data exists: Statistics need StatsBomb team stats (no possession/offsides are recorded, so they are never shown), Lineups need line-up rows, Events need minute-level events, Commentary has no data source so it never appears.
- **Own goals**: StatsBomb stores them under the scorer's team, martj42/fjelstul under the benefiting team; `/api/match-center` normalises this (`scoring_side`) and reports `goalsComplete` (recorded goals == final score); the scoreboard says when scorers may be incomplete.
- **Lineups**: positions come from `dim_player.primary_position` grouped to GK/DF/MF/FW; the pitch and the shape (e.g. 4-3-3) are derived from those counts, and the page falls back to a list when positions are missing. Managers are not in the data.
- **Status**: only Full time / Extra time / Penalties / Coming soon exist in the data; Live, Half Time, Postponed, Abandoned and Cancelled are supported by the badge but appear only if a source label says so (the live dot is never faked).
- **Flags**: `src/data/countries.ts` maps every team name (and spelling variants) to an ISO / flag-icons code; `components/CountryFlag.tsx` renders the SVG (flag-icons package). Defunct states (Yugoslavia, Serbia and Montenegro) and bracket placeholders (Winner Group A) get a neutral badge, never another country's flag. `tests/test_api.py::test_every_real_team_has_a_flag_or_is_an_explained_exception` checks every team in the data.
- **Themes**: the page theme (colours, banner art, pattern, logo) follows the edition shown, including on match pages and on fixtures filtered to one edition/competition. Colours come from each edition's logo, so the fixed navy/green palette of the brief was applied as the broadcast layout language, not as one palette for every page.

## Art direction (per-competition design languages)
Each competition has its own look, set from `frontend/src/theme/editions.ts` (`STYLE`) and `frontend/src/theme.css`: World Cup = Oswald, sharp angular panels and chamfered hero; Euro = Barlow Condensed, very round cards and a rounded hero; Copa América = Bebas Neue, skewed tabs and underlined section titles; Nations League = chamfered cards. Every edition adds its own logo, banner artwork, colours, ghost year lettering and pattern. The scoreboard and fixture cards use each nation's identity colours (`src/data/teamColors.json`, curated). Charts sit in a themed frame (title band, control strip) while the plot itself keeps the validated light palette. Animations respect the browser's reduce-motion setting.

## Line-ups and the Match analytics hub
- **Line-ups** (`components/match/FootballPitch.tsx`): every match with line-up data is drawn as a dark pitch with bright markings, one card per starter (position code and shirt number on the black header, a neutral silhouette in the team's kit colour, a yellow name tag) laid out by line (GK, defenders, defensive/central/attacking midfield, forwards) and left-to-right by recorded position, plus a banner with the flag, team name and the derived formation (e.g. 4-2-3-1). There are no player photos in the data, so avatars are neutral silhouettes, never invented faces. Players with only a general position (defender/midfielder/forward) keep their listed order and the page says so; matches without positions fall back to a list.
- **Match analytics** (`/analytics/matches`) is now a hub: filters, a scrolling rail of scoreboard cards, and the full Match Center (the same component as `/match/:key`) for the selected match, plus the edition's goal-timing chart.

## Managers and assists
- **Managers**: `python -m fbplatform.ingest.managers` builds `data/processed/match_managers.parquet` from StatsBomb match files, Wikipedia match boxes (cleaned of table markup) and, only as a labelled fallback, the tournament head coach from Wikipedia squad pages, then loads `wh.fact_match_managers` (also created by the full warehouse load). Coverage: 1,029 of 1,779 played matches have both managers (all World Cup, Euro and Copa editions in the data); the Nations League has no manager source, so it shows none. The Match Center shows the manager on each lineup banner and in the summary.
- **Assists**: every assist the sources record is shown: StatsBomb pass-to-goal links (World Cup 2018/2022, Euro 2020/2024, Copa 2024) and the martj42 assist column (mostly World Cup 2002–2014). Penalties and own goals have none; other editions record none, and the match page says so instead of showing blanks.
