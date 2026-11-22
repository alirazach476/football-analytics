# Data science report

_Generated 2026-11-22. Every number below is read from `reports/` at generation time._

## Scope and data

1,895 played matches (51 more fixtures are 'Coming soon' and excluded from every statistic and model target), 103 teams, 8,818 canonical players, 4,821 goals, 1,034,175 event rows across the FIFA World Cup, UEFA Euro, Copa América and UEFA Nations League. UEFA Champions League is out of scope. Per-match rates are used throughout; raw totals are never compared across editions of different size.

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
| Q1 | WC: goals per match (regulation) vs edition year | 552 | 1.05 [0.997, 1.11] | 0.198 | RR-1 (relative change per decade): 0.0528 |
| Q1 | EURO: goals per match (regulation) vs edition year | 261 | 0.942 [0.856, 1.04] | 0.44 | RR-1 (relative change per decade): -0.0582 |
| Q1 | COPA: goals per match (regulation) vs edition year | 224 | 0.942 [0.846, 1.05] | 0.44 | RR-1 (relative change per decade): -0.058 |
| Q2 | WC: knockout vs group/league, goals in regulation | 552 | -0.219 [-0.538, 0.114] | 0.274 | Cliff's delta (Cohen's d=-0.13): -0.0806 |
| Q2 | EURO: knockout vs group/league, goals in regulation | 261 | 0.405 [-0.0712, 0.857] | 0.274 | Cliff's delta (Cohen's d=0.27): 0.143 |
| Q2 | COPA: knockout vs group/league, goals in regulation | 224 | 0.648 [0.134, 1.15] | 0.0938 | Cliff's delta (Cohen's d=0.38): 0.218 |
| Q3 | WC: result of the team that scored first (W 350 / D 86 / L 56) | 492 | 0.711 [0.669, 0.751] | 1.36e-52 | win/(win+loss) share (0.5 = no edge): 0.862 |
| Q3 | EURO: result of the team that scored first (W 162 / D 46 / L 33) | 241 | 0.672 [0.609, 0.731] | 1.21e-21 | win/(win+loss) share (0.5 = no edge): 0.831 |
| Q3 | COPA: result of the team that scored first (W 158 / D 40 / L 18) | 216 | 0.731 [0.667, 0.789] | 7.85e-29 | win/(win+loss) share (0.5 = no edge): 0.898 |
| Q4 | Group-stage goals scored/match vs number of knockout matches played | 522 | 0.618 [0.557, 0.674] | 2.24e-56 | Spearman rho^2: 0.382 |
| Q4 | Group-stage goals scored/match vs points per match in the group stage | 522 | 0.731 [0.69, 0.766] | 3.44e-88 | Spearman rho^2: 0.535 |
| Q4 | Reaching the knockout stage ~ group-stage goals scored/match (+ competition) | 522 | 18.1 [10.9, 30.1] | 6.95e-29 | AUC (goals scored alone): 0.859 |
| Q5 | Group-stage goals conceded/match: progressed vs eliminated | 522 | -0.874 [-0.995, -0.755] | 8.29e-38 | Cliff's delta: -0.65 |
| Q5 | Joint logistic model: effect of goals conceded/match, adjusting for the other | 522 | 0.0396 [0.0198, 0.0792] | 7.64e-20 | standardised OR: 0.0792 |
| Q5 | Joint logistic model: effect of goals scored/match, adjusting for the other | 522 | 50.9 [23.2, 112] | 2.17e-22 | standardised OR: 18.3 |
| Q6 | Does the team listed first win more often? (71 shoot-outs) | 71 | 0.465 [0.345, 0.587] | 0.635 | deviation from 0.5: -0.0352 |
| Q6 | Does the team with the better record so far in that tournament win the shoot-out? | 62 | 0.597 [0.464, 0.719] | 0.324 | deviation from 0.5: 0.0968 |
| Q7 | WC: share of variance in edition performance explained by team identity (teams with >=3 ed | 221 | 0.329 [0.197, 0.449] | 0.00266 | ICC (0 = no consistency, 1 = fully consistent): 0.329 |
| Q7 | EURO: share of variance in edition performance explained by team identity (teams with >=3  | 116 | 0.128 [-0.0269, 0.242] | 0.0906 | ICC (0 = no consistency, 1 = fully consistent): 0.128 |
| Q7 | COPA: share of variance in edition performance explained by team identity (teams with >=3  | 107 | 0.479 [0.189, 0.67] | 0.00266 | ICC (0 = no consistency, 1 = fully consistent): 0.479 |
| Q8 | Of 101 knockout matches that went beyond 90 minutes, how many were still level after extra | 101 | 0.703 [0.604, 0.79] |  | share: 0.703 |
| Q8 | Goals per minute in extra time vs regulation, same 57 matches | 57 | 1.36 [0.907, 2.01] | 0.121 | rate ratio: 1.36 |
| Q8 | Is the team with the better record so far less likely to win when the match goes beyond 90 | 291 | 0.678 [0.406, 1.13] | 0.147 | phi coefficient: 0.0876 |
| Q9 | Absolute goal margin (regulation) differs between competitions (all matches) | 1851 | 0.00144 | 0.13 | epsilon-squared (0.01 small, 0.06 medium, 0.14 large): 0.00144 |
| Q9 | Pairwise (all matches): WC vs EURO mean margin | 813 | 0.0722 [-0.0949, 0.239] | 1 | Cliff's delta: 0.00512 |
| Q10 | WC: goals per match by format (WC-32: 448 matches, mean 2.48, WC-48: 104 matches, mean 2.8 | 552 | -0.402 [-0.796, -0.0299] | 0.138 | Cliff's delta: -0.123 |
| Q10 | WC: distribution of goals per match (0,1,2,3,4+) differs between formats | 552 | 5.28 | 0.779 | Cramer's V: 0.0978 |
| Q10 | EURO: goals per match by format (EURO-16: 113 matches, mean 2.64, EURO-24: 148 matches, me | 261 | 0.259 [-0.107, 0.639] | 0.485 | Cliff's delta: 0.0825 |

**Reading the results:** association is never causation; with n of 7–9 editions per competition, trend questions have low power; a non-significant result does not prove equality.

## Machine learning (test period)

| model | accuracy | 95% CI | log loss | ROC-AUC |
|---|---|---|---|---|
| baseline_prior | 0.449 | [0.390, 0.507] | 1.065 | 0.500 |
| baseline_elo_logreg | 0.596 | [0.541, 0.654] | 0.930 | 0.707 |
| logreg | 0.558 | [0.503, 0.617] | 0.948 | 0.665 |
| random_forest | 0.575 | [0.521, 0.634] | 0.957 | 0.682 |
| xgboost | 0.568 | [0.514, 0.623] | 0.956 | 0.691 |

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