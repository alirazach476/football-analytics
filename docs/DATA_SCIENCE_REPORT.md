# Data science report

_Generated 2026-11-06. Every number below is read from `reports/` at generation time._

## Scope and data

1,779 played matches (51 more fixtures are 'Coming soon' and excluded from every statistic and model target), 103 teams, 8,410 canonical players, 4,494 goals, 1,033,220 event rows across the FIFA World Cup, UEFA Euro, Copa América and UEFA Nations League. UEFA Champions League is out of scope. Per-match rates are used throughout; raw totals are never compared across editions of different size.

## Exploratory analysis: headline facts

| competition | editions | matches | goals/match | draw % | beyond 90 min % | avg attendance |
|---|---|---|---|---|---|---|
| FIFA World Cup | 7 | 488 | 2.61 | 23.0 | 8.6 | 53,115 |
| UEFA European Championship | 7 | 277 | 2.46 | 25.3 | 9.7 | 39,993 |
| Copa América | 9 | 248 | 2.51 | 27.4 | 9.7 | 32,088 |
| UEFA Nations League | 5 | 766 | 2.50 | 25.2 | 0.5 | 16,341 |

Nations League extra time is not recorded, so its 'beyond 90' share is understated.

Top scorers in the collected competitions (linked goals only; not career totals): Lionel Andrés Messi Cuccittini (35), Cristiano Ronaldo dos Santos Aveiro (25), Kylian Mbappé Lottin (23), Miroslav Klose (19), Harry Kane (15), Eduardo Jesús Vargas Rojas (15).

Full tables and figures: `reports/eda/eda_report.html` and the notebooks in `notebooks/`.

## Statistical investigation (10 required questions)

Assumptions were checked before choosing tests (goal counts are non-normal and over-dispersed → rank tests / quasi-Poisson). p-values are Holm-adjusted inside each family. Details, assumption diagnostics and limitations per analysis: `docs/STATISTICAL_REPORT.md`.

| Q | analysis | n | estimate [95% CI] | adj. p | effect size |
|---|---|---|---|---|---|
| Q1 | WC: goals per match (regulation) vs edition year | 488 | 1.09 [1.02, 1.17] | 0.0367 | RR-1 (relative change per decade): 0.0932 |
| Q1 | EURO: goals per match (regulation) vs edition year | 261 | 0.942 [0.856, 1.04] | 0.461 | RR-1 (relative change per decade): -0.0582 |
| Q1 | COPA: goals per match (regulation) vs edition year | 224 | 0.942 [0.846, 1.05] | 0.461 | RR-1 (relative change per decade): -0.058 |
| Q2 | WC: knockout vs group/league, goals in regulation | 488 | -0.262 [-0.611, 0.0854] | 0.274 | Cliff's delta (Cohen's d=-0.15): -0.0972 |
| Q2 | EURO: knockout vs group/league, goals in regulation | 261 | 0.405 [-0.0488, 0.851] | 0.274 | Cliff's delta (Cohen's d=0.27): 0.143 |
| Q2 | COPA: knockout vs group/league, goals in regulation | 224 | 0.648 [0.142, 1.18] | 0.0938 | Cliff's delta (Cohen's d=0.38): 0.218 |
| Q3 | WC: result of the team that scored first (W 311 / D 71 / L 50) | 432 | 0.72 [0.675, 0.762] | 1.07e-46 | win/(win+loss) share (0.5 = no edge): 0.861 |
| Q3 | EURO: result of the team that scored first (W 162 / D 46 / L 33) | 241 | 0.672 [0.609, 0.731] | 1.21e-21 | win/(win+loss) share (0.5 = no edge): 0.831 |
| Q3 | COPA: result of the team that scored first (W 158 / D 40 / L 18) | 216 | 0.731 [0.667, 0.789] | 7.85e-29 | win/(win+loss) share (0.5 = no edge): 0.898 |
| Q4 | Group-stage goals scored/match vs number of knockout matches played | 490 | 0.612 [0.548, 0.667] | 1.18e-51 | Spearman rho^2: 0.374 |
| Q4 | Group-stage goals scored/match vs points per match in the group stage | 490 | 0.724 [0.677, 0.761] | 2.16e-80 | Spearman rho^2: 0.524 |
| Q4 | Reaching the knockout stage ~ group-stage goals scored/match (+ competition) | 490 | 18.4 [10.8, 31.2] | 4.31e-27 | AUC (goals scored alone): 0.857 |
| Q5 | Group-stage goals conceded/match: progressed vs eliminated | 490 | -0.872 [-0.997, -0.751] | 1.19e-34 | Cliff's delta: -0.642 |
| Q5 | Joint logistic model: effect of goals conceded/match, adjusting for the other | 490 | 0.0378 [0.0183, 0.0782] | 9.33e-19 | standardised OR: 0.0753 |
| Q5 | Joint logistic model: effect of goals scored/match, adjusting for the other | 490 | 59.6 [25.7, 139] | 3.88e-21 | standardised OR: 20.6 |
| Q6 | Does the team listed first win more often? (68 shoot-outs) | 68 | 0.456 [0.335, 0.581] | 0.595 | deviation from 0.5: -0.0441 |
| Q6 | Does the team with the better record so far in that tournament win the shoot-out? | 59 | 0.576 [0.441, 0.704] | 0.595 | deviation from 0.5: 0.0763 |
| Q7 | WC: share of variance in edition performance explained by team identity (teams with >=3 ed | 194 | 0.334 [0.185, 0.452] | 0.00266 | ICC (0 = no consistency, 1 = fully consistent): 0.334 |
| Q7 | EURO: share of variance in edition performance explained by team identity (teams with >=3  | 116 | 0.128 [-0.0204, 0.257] | 0.0999 | ICC (0 = no consistency, 1 = fully consistent): 0.128 |
| Q7 | COPA: share of variance in edition performance explained by team identity (teams with >=3  | 107 | 0.479 [0.189, 0.67] | 0.00266 | ICC (0 = no consistency, 1 = fully consistent): 0.479 |
| Q8 | Of 97 knockout matches that went beyond 90 minutes, how many were still level after extra  | 97 | 0.701 [0.6, 0.79] |  | share: 0.701 |
| Q8 | Goals per minute in extra time vs regulation, same 53 matches | 53 | 1.42 [0.942, 2.12] | 0.0881 | rate ratio: 1.42 |
| Q8 | Is the team with the better record so far less likely to win when the match goes beyond 90 | 276 | 0.605 [0.358, 1.02] | 0.0777 | phi coefficient: 0.113 |
| Q9 | Absolute goal margin (regulation) differs between competitions (all matches) | 1735 | 0.00121 | 0.164 | epsilon-squared (0.01 small, 0.06 medium, 0.14 large): 0.00121 |
| Q9 | Pairwise (all matches): WC vs EURO mean margin | 749 | 0.0804 [-0.0971, 0.249] | 1 | Cliff's delta: 0.0121 |
| Q10 | WC: goals per match by format (WC-32: 384 matches, mean 2.45, WC-48: 104 matches, mean 2.8 | 488 | -0.431 [-0.812, -0.0393] | 0.0881 | Cliff's delta: -0.137 |
| Q10 | WC: distribution of goals per match (0,1,2,3,4+) differs between formats | 488 | 5.9 | 0.62 | Cramer's V: 0.11 |
| Q10 | EURO: goals per match by format (EURO-16: 113 matches, mean 2.64, EURO-24: 148 matches, me | 261 | 0.259 [-0.0997, 0.633] | 0.485 | Cliff's delta: 0.0825 |

**Reading the results:** association is never causation; with n of 7–9 editions per competition, trend questions have low power; a non-significant result does not prove equality.

## Machine learning (test period)

| model | accuracy | 95% CI | log loss | ROC-AUC |
|---|---|---|---|---|
| baseline_prior | 0.433 | [0.375, 0.491] | 1.075 | 0.500 |
| baseline_elo_logreg | 0.567 | [0.509, 0.622] | 0.942 | 0.711 |
| logreg | 0.542 | [0.484, 0.600] | 0.951 | 0.675 |
| random_forest | 0.556 | [0.498, 0.611] | 0.972 | 0.685 |
| xgboost | 0.575 | [0.520, 0.629] | 0.956 | 0.695 |

No tuned model is clearly better than the single-feature Elo baseline (overlapping intervals). See `docs/MODEL_DOCUMENTATION.md`.

## Advanced projects

* **Competitiveness index** (percentile construct, 0–1): highest EURO-2004, EURO-2024, UNL-2020-21; lowest WC-2026, COPA-2024, COPA-2007. Differences of a few hundredths are within noise (bootstrap interval on the margin component is in the table).
* **Team dominance** (editions ≥ 3, shrunk win %, goal difference, knockout record, progression, titles): Argentina, Spain, France, Brazil, Germany, Greece.
* **Trend forecasts (EXPLORATORY, not reliable):** WC 2030: 2.90 goals/match [2.61, 3.19] via linear_trend; EURO 2028: 2.49 goals/match [2.03, 2.95] via naive_mean; COPA 2028: 2.62 goals/match [1.79, 3.44] via naive_mean; UNL 2028: 2.51 goals/match [2.16, 2.85] via naive_mean. Methods were chosen by leave-last-out backtest on 4–6 origins.
* **Head-to-head tool:** `fbplatform.analysis.advanced.head_to_head(a, b, competition=None, since=None)`; meetings are not equivalent contexts and the output says so.

## Limitations

* Tournament football produces few matches per team per edition: team-level estimates are noisy.
* Player statistics cover only the collected competitions; assists and per-90 rates are partial (see DATA_QUALITY.md).
* Elo is built from these four competitions only (no friendlies/qualifiers) and is therefore a partial strength measure.
* Format changes (24→48 teams at the World Cup) are confounded with era.
* The Nations League has the weakest event coverage; any player-level conclusion excludes its scorers.