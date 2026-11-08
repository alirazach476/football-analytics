# Visualization guide

The **Visualization lab** is a second group of dashboard pages (sidebar → "Visualization lab") built on reusable chart functions in `src/fbplatform/viz/`. Competitions covered: FIFA World Cup, UEFA Euro, Copa América, UEFA Nations League. The UEFA Champions League is excluded everywhere (a test checks that no chart data contains it).

```bash
docker compose up -d && set PYTHONPATH=src && python -m fbplatform.orchestration.steps     # data + warehouse
streamlit run src/fbplatform/dashboard/app.py                                                  # pages: Analytics + Visualization lab
```

## Design principles (and how they are enforced)

| Principle | How |
|---|---|
| **Never fabricate** | A chart is drawn only when the fields it needs exist; otherwise it returns an *unavailable* result with the reason, shown as "Not shown: …". Tests prove it (no shot map for World Cup 2002, no passing network for Wyscout matches, no score progression when goal events don't reproduce the score, no assists for editions that don't record them). |
| **Missing ≠ zero** | Missing is blank/NULL and reported separately from genuine zeros (attendance 0 = closed doors; a team that did not take part in an edition is a blank heat-map cell, not 0; a knockout record from fewer than 3 matches is blank). Fixtures not played yet are excluded from missing-value measures: they are not data gaps. |
| **Upcoming fixtures** | Never part of any statistic. In brackets and the match selector they appear as **Coming soon** with the known details. |
| **Right chart for the question** | Magnitudes = bars from zero; change over time = lines; distributions = histograms/box/violin; association = scatter with fit and interval; uncertainty = intervals; log-scale counts = dots (a bar's length on a log axis depends on an arbitrary baseline); no dual axes anywhere. |
| **Honest scales and labels** | Axis titles carry units; every chart shows its sample size with the correct unit (matches, players, shots, features…), its source and its limitations under the chart; intervals are drawn where a number is an estimate. |
| **Colour** | One validated palette (colour-blind safe, checked with the palette validator). A competition keeps its colour and marker shape in every chart; magnitude = one blue ramp; polarity = blue↔red around a neutral grey; outcome win/draw/loss = blue/grey/orange. Four competitions exceed the all-pairs colour limit, so marker **shapes** are a second encoding. Yellow/aqua are below 3:1 contrast on white, so those charts also have direct labels or a table view. |
| **Table view for every chart** | Each chart has "Table view and downloads": the exact data behind it. |

## Chart catalogue

`C` = `fbplatform.viz.<module>.<function>`. Every function returns a `Chart` (figure, data, n, source, note, optional Matplotlib twin).

### 1. Competition analytics — `viz.competition`
| Chart | Function | Needs / not shown when |
|---|---|---|
| Historical goals and matches (per edition; goals per match) | `competition.edition_history` | no played editions in the selection |
| Champions and runner-up history, title counts | `competition.champions_timeline`, `competition.title_counts` | edition without a decided final is absent, not blank |
| Edition comparison (bars) and z-score heat-map within each competition | `competition.edition_comparison`, `competition.edition_heatmap` | heat-map needs editions with 20+ played matches |
| Tournament progression (teams reaching each stage) | `competition.progression_funnel` | edition without a played knockout stage |
| Group standings (derived) | `competition.group_standings` | competitions/editions without groups; labelled DERIVED (3-1-0, tie-break points/GD/GF only) |
| Knockout bracket (feeders adjacent, winners bold, penalties) | `competition.knockout_bracket` | league formats; future matches shown as *Coming soon* |
| Goal-scoring distributions (share of matches by goals; by minute band) | `competition.goal_distribution`, `competition.goal_minutes` | <30 matches / <50 goal events with a minute |

### 2. Team analytics — `viz.teams`
| Chart | Function | Needs / not shown when |
|---|---|---|
| Win/draw/loss distribution | `teams.wdl_distribution` | no team with the minimum matches |
| Goals scored vs conceded | `teams.goals_scored_conceded` | fewer than 2 teams |
| Radar (percentiles among teams with 15+ matches) | `teams.radar` | needs ≥ 8 reference teams; missing metrics are gaps |
| Comparison heat-map; points-per-match by edition heat-map | `teams.comparison_heatmap`, `teams.edition_heatmap` | blank = did not play / too few matches |
| Historical performance timeline | `teams.timeline` | — |
| Head-to-head (by competition + every meeting) | `teams.head_to_head` | same team twice / no meetings |
| Rankings with confidence intervals; strength vs consistency | `teams.rankings`, `teams.consistency` | minimum matches/editions |

### 3. Player analytics — `viz.players` (collected competitions only, not careers)
| Chart | Function | Needs / not shown when |
|---|---|---|
| Top scorers / assist providers | `players.top_players` | assists only in editions with event-level data |
| Goals / assists per 90 vs minutes | `players.per90` | players with ≥ N *known* minutes; goals counted only in matches with known minutes |
| Player comparison radar (percentile within position) | `players.radar` | only players with 270+ minutes of event data |
| Performance trends | `players.trends` | a gap = did not play; a point at 0 = played, did not score |
| Age vs performance; position comparison | `players.age_vs_performance`, `players.position_comparison` | players with a known date of birth / position (others omitted, not guessed) |
| Player contribution index | `players.contribution` | players with 900+ known minutes |

### 4. Match analytics — `viz.matches`
| Chart | Function | Needs / not shown when |
|---|---|---|
| Goal timeline; match event timeline (goals, cards, substitutions) | `matches.goal_timeline`, `matches.event_timeline` | only events present in the source are drawn |
| Score progression | `matches.score_progression` | goal events must reproduce the recorded score |
| Scoreline heat-map; outcome distribution | `matches.scoreline_heatmap`, `matches.outcome_distribution` | — |
| Shot maps | `matches.shot_map` | shot coordinates: only the 313 StatsBomb/Wyscout matches (WC 2018/22, Euro 2016/20/24, Copa 2024); xG only for StatsBomb |
| Passing networks | `matches.passing_network` | pass **recipients** (StatsBomb only) |
| Home/away comparison | `matches.home_away` | "own country" vs neutral venue; says why 'listed first' is not 'home' |
| Penalty-shoot-out analysis (per edition, scores, team records with Wilson intervals) | `matches.shootouts` | kick scores known for 52 of 68 shoot-outs |

### 5. Statistical analysis — `viz.statplots` (Matplotlib/Seaborn twin for PNG)
Correlation matrix `statplots.correlation_matrix` · distribution `statplots.distribution` · box `statplots.box_plot` · violin `statplots.violin_plot` · scatter with regression and CI band `statplots.scatter_regression` · confidence-interval forest plots `statplots.ci_forest` · hypothesis-test summary `statplots.hypothesis_summary` · regression diagnostics (residuals, Q–Q, scale–location, leverage/Cook's) `statplots.regression_diagnostics`. Test results come from `reports/statistics/results.csv`.

### 6. Machine learning — `viz.mlplots` (saved models, nothing retrained)
Confusion matrix `mlplots.confusion` · ROC `mlplots.roc_curves` · precision–recall `mlplots.pr_curves` · permutation/gain importance `mlplots.feature_importance` · SHAP bar/beeswarm/dependence `mlplots.shap_bar`, `mlplots.shap_beeswarm`, `mlplots.shap_dependence` · predicted vs actual (calibration; expected vs actual goals) `mlplots.calibration`, `mlplots.goals_actual_vs_predicted` · residuals `mlplots.residual_plots` · clustering (PCA scatter, dendrogram, silhouette, players) `mlplots.team_cluster_scatter`, `mlplots.team_dendrogram`, `mlplots.silhouette_by_k`, `mlplots.player_cluster_scatter` · model comparison `mlplots.model_comparison`, `mlplots.goal_model_comparison`. Curves are computed from the saved models on the chronological **test** period; a test checks that they reproduce the accuracies recorded in the model report. Everything is labelled as a prediction.

### 7. Data engineering — `viz.engineering`
Bronze/Silver/Gold record counts `engineering.layer_record_counts` · completeness `engineering.completeness_bars` · missing-value heat-map `engineering.missing_heatmap` · duplicates `engineering.duplicates` · pipeline execution times and failures `engineering.pipeline_durations`, `engineering.pipeline_failures` · data freshness `engineering.freshness` · source coverage `engineering.source_coverage` · data-quality trends `engineering.dq_trends`.

## Interactive capabilities

| Capability | Where |
|---|---|
| Competition, edition/season, stage, team and date-range filters; reset | one shared sidebar block on every page (`dashboard/viz_ui.py:sidebar_filters`); each page shows the resulting sample size |
| Player filters | Players page: name search + multi-select |
| Cross-filtering | click an edition on the history chart → progression, standings and bracket follow; click bubbles on the team scatter → radar, heat-map and timeline follow |
| Download filtered data (CSV) | sidebar button for the filtered matches/players; "Table view and downloads" under every chart (CSV of the exact chart data) |
| Download charts | **HTML** (interactive, self-contained) for every chart; **PNG** from the Matplotlib/Seaborn twin where one exists (competition history, goal distribution, correlation, distributions, box, violin, scatter, diagnostics); for the rest the camera icon in the chart toolbar downloads a PNG of the interactive chart (server-side PNG of Plotly needs the optional `kaleido` package) |
| Tooltips | every mark has a hover tooltip with the raw values and sample size |
| Responsive | wide layout, charts resize to the page width, controls in the sidebar |

## Adding a chart

1. Write `def my_chart(df, ...) -> Chart` in the right `viz/` module: check the required fields first and `return unavailable(name, "reason")` if they are missing; build the figure with `common.style(...)`; return the exact data behind it.
2. Add its unit to `common.UNITS` if the sample is not "matches".
3. Render it with `viz_ui.render(chart, key)` on a page; add a test to `tests/test_viz.py` (data correctness + the unavailable case + Arrow-serialisable table).

## Tests (`tests/test_viz.py`, 35 tests)
Filters (synthetic data); furthest stage, bracket feeder structure and winner links against known results; upcoming bracket = *Coming soon*; group standings arithmetic; histograms sum to 100%; shot maps/passing networks only from real coordinates/recipients and spot-checked against raw passes; score progression refuses tampered events; missing never drawn as zero; team/radar consistency; head-to-head equals the head-to-head tool; shoot-out totals (68 / 52); correlation symmetry; Matplotlib twins render; CI and hypothesis charts use only valid rows; ML curves reproduce the saved accuracies; SHAP shapes; engineering charts equal the monitoring tables; CSV/HTML/PNG export; no Champions League in any chart data; every chart's table view is Arrow-serialisable; all 7 pages render; filters change the sample; cross-filter default; the match page defaults to a played match.
