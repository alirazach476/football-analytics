# Model documentation

_Generated 2026-11-22. Models are saved in `models/` (joblib + JSON metadata); runs are tracked in MLflow (`mlflow ui --backend-store-uri sqlite:///mlflow.db`)._

## Rules applied to every model

* **No leakage:** a match's features use only matches from strictly earlier dates (same-day results never leak). `tests/test_ml.py` changes all later results and verifies earlier features do not move.
* **Chronological evaluation:** train / validation / test are separated by date. Hyper-parameters are tuned only on the training period with expanding-window time-series CV.
* **Scheduled fixtures are never used** as training or evaluation targets (no outcome exists).
* **Predictions are labelled** 'MODEL PREDICTION' everywhere they appear.
* LightGBM is not installed here and was not evaluated.

## 1. Match outcome (A win / draw / B win)

* **Target:** result of the team listed first on the recorded score (extra time included, shoot-out excluded). **Rows:** played matches with both teams known.
* **Split:** train 1998-06-10 → 2022-11-28 (1326), validation → 2024-11-19 (277), test 2025-03-20 → 2026-11-17 (292).
* **Features (52):** per-team past win %, points/match, goals for/against, goal difference, clean sheets, last-5 form, tournament experience (earlier editions), knockout record, attack/defence strength (relative to the league average so far), rest days, Elo; pairwise differences; head-to-head record; stage, knockout flag, host flags, competition.
* **Elo:** computed only from earlier matches in these four competitions (start 1500, K by competition, goal-difference multiplier, +100 for the host). Partial strength measure, not the official World Football Elo.
* **Selection:** lowest validation log loss → **xgboost**, refit on train+validation.

| model | accuracy [95% CI] | macro-F1 | log loss [95% CI] | ROC-AUC (OvR) |
|---|---|---|---|---|
| baseline_prior | 0.449 [0.390, 0.507] | 0.206 | 1.065 [1.040, 1.089] | 0.500 |
| baseline_elo_logreg | 0.596 [0.541, 0.654] | 0.445 | 0.930 [0.888, 0.973] | 0.707 |
| logreg | 0.558 [0.503, 0.617] | 0.452 | 0.948 [0.891, 1.003] | 0.665 |
| random_forest | 0.575 [0.521, 0.634] | 0.439 | 0.957 [0.914, 1.002] | 0.682 |
| xgboost | 0.568 [0.514, 0.623] | 0.441 | 0.956 [0.911, 1.000] | 0.691 |

Final selected model on the test period (refit on train+validation): accuracy 0.579, log loss 0.950, ROC-AUC 0.686.

**Interpretation:** the features carry real signal (every model beats the class prior), but none is clearly better than the one-feature Elo baseline — the intervals overlap. Draws are almost never predicted (draw recall on the test period is 0-4% for every model; see `confusion_matrices_test.csv`). Do not read these as betting-grade probabilities.

## 2. Goal prediction (expected goals per team, regulation time)

* **Selected:** poisson_regression (lowest validation Poisson deviance). Diagnostics: {'pearson_dispersion': 1.2113941952090395, 'zero_share_observed': 0.29037800687285226, 'zero_share_poisson_expected': 0.29678690583885486}.
* Baseline = training mean. Metrics: MAE, RMSE (team and total goals), Poisson deviance, dispersion, zero share, calibration by decile.

| model | MAE team goals | RMSE team goals | Poisson deviance | MAE total goals |
|---|---|---|---|---|
| baseline_train_mean | 1.031 | 1.364 | 1.424 | 1.397 |
| poisson_regression | 0.932 | 1.267 | 1.238 | 1.373 |
| random_forest | 0.957 | 1.273 | 1.257 | 1.391 |
| xgboost | 0.943 | 1.270 | 1.251 | 1.378 |

**Over/under 2.5 (analytical experiment, independent-Poisson assumption):** accuracy 0.512 vs base rate 0.540; Brier 0.249 vs 0.256. Goal totals are barely predictable beyond the base rate.

## 3. Team clustering

K-Means / Ward / DBSCAN on standardised team features (goals for/against, win %, points, goal difference, clean sheets, goal-difference SD, edition-to-edition SD). k = 2 by silhouette (0.30); cophenetic correlation 0.50; DBSCAN found 2 clusters and 23 noise teams; bootstrap stability ARI 0.83. The structure is weak: teams form a continuum. Cluster names come from explicit rules over the standardised centroids and the profile tables are saved beside them. Possession is not available.

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