# Model documentation

_Generated 2026-11-06. Models are saved in `models/` (joblib + JSON metadata); runs are tracked in MLflow (`mlflow ui --backend-store-uri sqlite:///mlflow.db`)._

## Rules applied to every model

* **No leakage:** a match's features use only matches from strictly earlier dates (same-day results never leak). `tests/test_ml.py` changes all later results and verifies earlier features do not move.
* **Chronological evaluation:** train / validation / test are separated by date. Hyper-parameters are tuned only on the training period with expanding-window time-series CV.
* **Scheduled fixtures are never used** as training or evaluation targets (no outcome exists).
* **Predictions are labelled** 'MODEL PREDICTION' everywhere they appear.
* LightGBM is not installed here and was not evaluated.

## 1. Match outcome (A win / draw / B win)

* **Target:** result of the team listed first on the recorded score (extra time included, shoot-out excluded). **Rows:** played matches with both teams known.
* **Split:** train 2000-06-10 → 2022-11-23 (1242), validation → 2024-11-15 (262), test 2024-11-16 → 2026-10-06 (275).
* **Features (52):** per-team past win %, points/match, goals for/against, goal difference, clean sheets, last-5 form, tournament experience (earlier editions), knockout record, attack/defence strength (relative to the league average so far), rest days, Elo; pairwise differences; head-to-head record; stage, knockout flag, host flags, competition.
* **Elo:** computed only from earlier matches in these four competitions (start 1500, K by competition, goal-difference multiplier, +100 for the host). Partial strength measure, not the official World Football Elo.
* **Selection:** lowest validation log loss → **xgboost**, refit on train+validation.

| model | accuracy [95% CI] | macro-F1 | log loss [95% CI] | ROC-AUC (OvR) |
|---|---|---|---|---|
| baseline_prior | 0.433 [0.375, 0.491] | 0.201 | 1.075 [1.051, 1.101] | 0.500 |
| baseline_elo_logreg | 0.567 [0.509, 0.622] | 0.430 | 0.942 [0.897, 0.988] | 0.711 |
| logreg | 0.542 [0.484, 0.600] | 0.442 | 0.951 [0.893, 1.013] | 0.675 |
| random_forest | 0.556 [0.498, 0.611] | 0.421 | 0.972 [0.931, 1.016] | 0.685 |
| xgboost | 0.575 [0.520, 0.629] | 0.443 | 0.956 [0.910, 1.002] | 0.695 |

Final selected model on the test period (refit on train+validation): accuracy 0.564, log loss 0.946, ROC-AUC 0.702.

**Interpretation:** the features carry real signal (every model beats the class prior), but none is clearly better than the one-feature Elo baseline — the intervals overlap. Draws are almost never predicted (draw recall on the test period is 0-4% for every model; see `confusion_matrices_test.csv`). Do not read these as betting-grade probabilities.

## 2. Goal prediction (expected goals per team, regulation time)

* **Selected:** poisson_regression (lowest validation Poisson deviance). Diagnostics: {'pearson_dispersion': 1.1436750955548032, 'zero_share_observed': 0.3010948905109489, 'zero_share_poisson_expected': 0.293175588591258}.
* Baseline = training mean. Metrics: MAE, RMSE (team and total goals), Poisson deviance, dispersion, zero share, calibration by decile.

| model | MAE team goals | RMSE team goals | Poisson deviance | MAE total goals |
|---|---|---|---|---|
| baseline_train_mean | 1.034 | 1.371 | 1.451 | 1.416 |
| poisson_regression | 0.935 | 1.255 | 1.230 | 1.388 |
| random_forest | 0.957 | 1.272 | 1.261 | 1.402 |
| xgboost | 0.955 | 1.268 | 1.257 | 1.405 |

**Over/under 2.5 (analytical experiment, independent-Poisson assumption):** accuracy 0.526 vs base rate 0.522; Brier 0.246 vs 0.255. Goal totals are barely predictable beyond the base rate.

## 3. Team clustering

K-Means / Ward / DBSCAN on standardised team features (goals for/against, win %, points, goal difference, clean sheets, goal-difference SD, edition-to-edition SD). k = 2 by silhouette (0.29); cophenetic correlation 0.47; DBSCAN found 2 clusters and 17 noise teams; bootstrap stability ARI 0.68. The structure is weak: teams form a continuum. Cluster names come from explicit rules over the standardised centroids and the profile tables are saved beside them. Possession is not available.

## 4. Player clustering

Per-90 StatsBomb features, clustered **within position** (defenders, midfielders, forwards); goalkeepers are profiled separately.

| position | players | k | silhouette | stability ARI |
|---|---|---|---|---|
| Defender | 338 | 2 | 0.23 | 0.74 |
| Midfielder | 225 | 2 | 0.23 | 0.90 |
| Forward | 178 | 3 | 0.14 | 0.57 |

Silhouettes are low: the groups are descriptive, not distinct player types.

## 5. Player performance analysis

**Association** (explains goals per 90; grouped cross-validation by player):

| model | n | CV R² | CV MAE | baseline MAE |
|---|---|---|---|---|
| ridge | 4010 | 0.262 | 0.119 | 0.152 |
| gradient_boosting | 4010 | 0.278 | 0.114 | 0.152 |

**Prediction** of next-tournament goals per 90 (train ≤ 2016, test later):

| model | MAE | R² | Spearman |
|---|---|---|---|
| baseline_train_mean | 0.163 | -0.001 |  |
| baseline_last_edition_rate | 0.137 | -0.267 | 0.35 |
| ridge | 0.133 | 0.269 | 0.46 |
| random_forest | 0.125 | 0.263 | 0.47 |

Position (forward) dominates; `team_gf_pm` is partly mechanical (a player's goals are part of the team's goals). No claim about player quality is made.

## Explainability

Permutation importance (test period), XGBoost gain, SHAP (mean |impact| per outcome) and partial-dependence tables are in `reports/ml/outcome/` and shown on the dashboard's Machine-learning page. Importances describe the model, not football causation.

## Using the models

```python
from fbplatform.ml.outcome import predict_matchup
predict_matchup('Argentina', 'France', as_of='2026-07-01', competition='WC', stage_name='Final')
```
Returns probabilities built only from matches before `as_of`, labelled as a model prediction. The 51 Euro 2028 fixtures cannot be predicted until their teams are known.