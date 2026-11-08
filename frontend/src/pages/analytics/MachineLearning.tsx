import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { predict, useApiQuery } from "../../api";
import { Callout, PageHeader, Tabs } from "../../components/ui";
import { SelectField } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import QuickPlot from "../../components/QuickPlot";
import { Block, Loading, PredictionBanner, T, pick, useTable } from "./kit";

const r3 = (t: any) => t && ({ ...t, rows: t.rows.map((r: any) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, typeof v === "number" && !Number.isInteger(v) ? Math.round(v * 1000) / 1000 : v]))) });
const COLS = ["A win", "draw", "B win"];

function Predictor() {
  const teams = useApiQuery<string[]>("team_names").data ?? [];
  const [a, setA] = useState("Argentina"); const [b, setB] = useState("France"); const [date, setDate] = useState("2026-07-01"); const [stage, setStage] = useState("Group stage");
  const mut = useMutation({ mutationFn: () => predict({ a, b, as_of: date, competition: "WC", stage }) });
  const p = mut.data;
  return (
    <div>
      <p className="mb-4 text-sm">Probabilities for a <b>hypothetical</b> meeting, built only from matches before the chosen date. This is a model prediction, not a result.</p>
      <div className="card mb-5 flex flex-wrap items-end gap-4 p-4">
        <SelectField label="Team A" value={a} onChange={setA} options={teams} /><SelectField label="Team B" value={b} onChange={setB} options={teams} />
        <label><span className="label">As of date</span><input className="field" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <SelectField label="Stage" value={stage} onChange={setStage} options={["Group stage", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]} />
        <button className="btn btn-primary" disabled={a === b || mut.isPending} onClick={() => mut.mutate()}>{mut.isPending ? "Predicting…" : "Predict"}</button>
      </div>
      {a === b && <Callout tone="info">Choose two different teams.</Callout>}
      {mut.isError && <Callout tone="warn">{(mut.error as Error).message}</Callout>}
      {p && <><QuickPlot data={[{ type: "bar", x: Object.keys(p.probabilities), y: Object.values(p.probabilities), text: Object.values(p.probabilities).map((v: any) => `${Math.round(v * 100)}%`), textposition: "outside", marker: { color: ["#2a78d6", "#94a3b8", "#d9822b"] } }]}
        layout={{ title: { text: "PREDICTION — outcome probabilities" }, yaxis: { range: [0, 1], tickformat: ".0%", gridcolor: "rgba(15,23,42,.08)" } }} caption={`${p.label} · uses only matches before ${p.based_on_matches_before}`} /></>}
    </div>
  );
}

export default function MachineLearning() {
  const [tab, setTab] = useState("Match outcome"); const meta = useApiQuery<any>("ml_meta").data;
  const cmp = useTable("ml_outcome_comparison"); const imp = useApiQuery<any>("ml_importance").data; const preds = useTable("ml_outcome_predictions"); const goals = useApiQuery<any>("ml_goals").data; const cl = useApiQuery<any>("ml_clusters").data;
  const models = useApiQuery<any>("ml_meta").data && (imp?.confusion?.rows ?? []).map((r: any) => r.model) as string[];
  const [cmModel, setCmModel] = useState(""); const [pdpFeat, setPdpFeat] = useState("");
  const test = useMemo(() => cmp.table && ({ ...cmp.table, rows: cmp.rows.filter((r) => r.split === "test") }), [cmp]);
  const feats = useMemo(() => Array.from(new Set<string>((imp?.pdp?.rows ?? []).map((r: any) => r.feature))), [imp]);
  const pdp = (imp?.pdp?.rows ?? []).filter((r: any) => r.feature === (pdpFeat || feats[0]));
  const outcomes = Array.from(new Set<string>(pdp.map((r: any) => r.outcome)));
  const calib = goals?.calibration?.rows ?? [];
  const sp = meta?.split;
  if (meta === undefined) return <Loading h={300} />;
  if (!meta || !Object.keys(meta).length) return <Callout tone="warn" title="No trained models found">Run <code>python -m fbplatform.ml.outcome</code> first.</Callout>;
  const mm = cmModel || models?.[0];
  return (
    <div>
      <PageHeader title="Machine learning" /><PredictionBanner />
      <Tabs tabs={["Match outcome", "Goals", "Explainability", "Clustering", "Try a matchup"]} value={tab} onChange={setTab} id="ml" />
      <div className="pt-6">
        {tab === "Match outcome" && <>
          {sp && <p className="mb-4 text-sm">Chronological split: train {sp.train[0]} → {sp.train[1]} ({sp.train[2]} matches), validation → {sp.validation[1]} ({sp.validation[2]}), test {sp.test[0]} → {sp.test[1]} ({sp.test[2]}). Selected on validation log loss: <b>{meta.selected_model}</b>.{meta.lightgbm ? "" : " LightGBM was not available."}</p>}
          <T t={r3(pick(test, ["model", "accuracy", "accuracy_ci_low", "accuracy_ci_high", "f1_macro", "log_loss", "log_loss_ci_low", "log_loss_ci_high", "roc_auc_ovr"]))} searchable={false} filename="ml_test_metrics" />
          <div className="mt-5"><ChartSection spec={{ id: "ml.cmp", title: "Test log loss with 95% bootstrap interval (lower is better)", fixed: { metric: "log_loss" } }} /></div>
          <Callout tone="info" className="mb-6">The intervals overlap: no complex model is clearly better than the one-feature Elo baseline on this test set. Accuracy of ~55% on three outcomes is realistic for tournament football.</Callout>
          {mm && <ChartSection key={mm} spec={{ id: "ml.confusion", title: "Confusion matrix (test period)", fixed: { model: mm, norm: false }, params: [{ key: "model", label: "Model", type: "select", options: models ?? [], default: mm }] }} />}
          <Block title="Out-of-sample predictions vs what happened" hint="'A' = team listed first. Every row was predicted from matches played before it. Fixtures whose teams are not decided yet cannot be predicted.">
            <T t={r3({ ...(preds.table as any), columns: ["match_date", "season_id", "team_a", "team_b", "p_A_win", "p_draw", "p_B_win", "PREDICTION", "actual result (A/D/B)"], rows: preds.rows.map((r) => ({ ...r, PREDICTION: r.predicted, "actual result (A/D/B)": r.result })) })} filename="ml_predictions" pageSize={15} />
          </Block>
        </>}
        {tab === "Goals" && (!goals ? <Loading /> : <>
          <T t={r3(goals.comparison)} searchable={false} filename="goal_models" />
          <Block title="Count-model diagnostics (selected model, test period)"><T t={r3(goals.diagnostics)} searchable={false} filename="goal_diagnostics" /></Block>
          <QuickPlot data={[{ type: "scatter", mode: "markers", x: calib.map((r: any) => r.mean_predicted), y: calib.map((r: any) => r.mean_observed), marker: { size: calib.map((r: any) => Math.max(8, Math.sqrt(r.n) * 2)), color: "#2a78d6" }, name: "deciles" },
            { type: "scatter", mode: "lines", x: [0, 2.5], y: [0, 2.5], line: { dash: "dash", color: "#64748b" }, name: "perfect calibration" }]}
            layout={{ title: { text: "Calibration: predicted vs observed goals per team (deciles)" }, xaxis: { title: { text: "Mean predicted goals" } }, yaxis: { title: { text: "Mean observed goals" } } }} caption="Points on the dashed line mean the model's expected goals match what happened." />
          <Block title="Over/under 2.5 goals: an analytical experiment"><T t={r3(goals.over_under)} searchable={false} filename="over_under" />
            <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Model accuracy for over/under is essentially the base rate: goal totals are very hard to predict.</p></Block>
          <Block title="Expected goals: PREDICTED vs actual (first 40 test matches)"><T t={r3({ ...goals.expected, columns: goals.expected.columns.filter((c: string) => c !== "note").map((c: string) => c === "predicted_expected_goals" ? "PREDICTED expected goals" : c === "goals" ? "actual goals" : c), rows: goals.expected.rows.slice(0, 40).map((r: any) => { const { note, predicted_expected_goals, goals: g, ...rest } = r; return { ...rest, "PREDICTED expected goals": predicted_expected_goals, "actual goals": g }; }) })} filename="expected_goals" pageSize={20} /></Block>
          <ChartSection spec={{ id: "ml.gcmp", title: "Goal-model comparison", fixed: { metric: "poisson_deviance" } }} />
        </>)}
        {tab === "Explainability" && (!imp ? <Loading /> : <>
          <ChartSection spec={{ id: "ml.imp_perm", title: "Permutation importance (drop in test log-loss score when a feature is shuffled)" }} />
          {imp.shap?.rows?.length > 0 && <ChartSection spec={{ id: "ml.shap_bar", title: "SHAP: mean |impact| per outcome (XGBoost)" }} />}
          <Block title="Partial dependence">
            <div className="mb-3 max-w-xs"><SelectField label="Feature" value={pdpFeat || feats[0]} onChange={setPdpFeat} options={feats} /></div>
            <QuickPlot data={outcomes.map((o) => ({ type: "scatter", mode: "lines+markers", name: o, x: pdp.filter((r: any) => r.outcome === o).map((r: any) => r.value), y: pdp.filter((r: any) => r.outcome === o).map((r: any) => r.partial_dependence) }))}
              layout={{ title: { text: `Partial dependence: ${pdpFeat || feats[0]}` }, xaxis: { title: { text: "feature value" } }, yaxis: { title: { text: "partial dependence" } } }} />
          </Block>
          <p className="text-xs" style={{ color: "var(--c-muted)" }}>Importance describes the model, not football causality. 'editions' = number of earlier tournament editions the team played, a proxy for tournament experience.</p>
        </>)}
        {tab === "Clustering" && (!cl ? <Loading /> : <>
          {cl.team_summary?.rows?.[0] && <p className="mb-4 text-sm">Selected k = {cl.team_summary.rows[0].k_selected} (silhouette {Number(cl.team_summary.rows[0].silhouette_kmeans).toFixed(2)}); bootstrap stability ARI {Number(cl.team_summary.rows[0].bootstrap_stability_mean_ari).toFixed(2)}. The structure is weak: teams form a continuum, not distinct types.</p>}
          <T t={pick(cl.team_profiles, ["kmeans", "n_teams", "gf_pm", "ga_pm", "win_pct", "suggested_description", "members"])} searchable={false} filename="team_clusters" />
          <div className="mt-5"><ChartSection spec={{ id: "ml.team_clusters", title: "Team clusters (goals scored vs conceded per match)" }} /></div>
          <details className="card mb-6 p-4"><summary className="cursor-pointer font-semibold">Exploratory finer split (k=4, lower silhouette)</summary><div className="mt-3"><T t={pick(cl.team_k4, ["k4", "n_teams", "gf_pm", "ga_pm", "win_pct", "suggested_description", "members"])} searchable={false} filename="team_k4" /></div></details>
          <Block title="Players (K-Means within position, StatsBomb-covered matches only)"><T t={pick(cl.player_profiles, ["position", "cluster", "n_players", "goals_p90", "assists_p90", "tackles_p90", "description", "examples"])} filename="player_clusters" /></Block>
        </>)}
        {tab === "Try a matchup" && <Predictor />}
      </div>
    </div>
  );
}
