import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLookups } from "../../api";
import { Callout, PageHeader, Tabs } from "../../components/ui";
import { Row, Segmented, SelectField, Toggle } from "../../components/controls";
import { PredictionBanner } from "../analytics/kit";
import { Charts } from "./labkit";

const CLS: [number, string][] = [[0, "A win"], [1, "draw"], [2, "B win"]];

export default function LabMl() {
  const { data: lk } = useLookups(); const models = lk?.models ?? []; const [tab, setTab] = useState("Classification");
  const feats = useQuery({ queryKey: ["shapfeat"], queryFn: async () => (await fetch("/api/lab/shap-features")).json() as Promise<string[]>, staleTime: Infinity }).data ?? [];
  const [model, setModel] = useState<string>(); const [norm, setNorm] = useState(true); const [cls, setCls] = useState(0); const [cls2, setCls2] = useState(0); const [feat, setFeat] = useState<string>();
  const [m2, setM2] = useState<string>(); const [k2, setK2] = useState(0); const [pos, setPos] = useState("Forward"); const [met, setMet] = useState("log_loss"); const [gm, setGm] = useState("poisson_deviance");
  const last = models[models.length - 1]; const mm = model ?? last; const mm2 = m2 ?? last; const fe = feat ?? (feats.includes("elo_diff") ? "elo_diff" : feats[0]);
  return (
    <div>
      <PageHeader eyebrow="Visualization lab" title="Machine-learning visualisations" subtitle="All curves and matrices come from the SAVED models applied to the chronological test period (nothing is retrained here). The test period was never used for training or tuning." />
      <PredictionBanner />
      {lk && !models.length ? <Callout tone="warn" title="No saved models found">Run <code>python -m fbplatform.ml.outcome</code> and <code>python -m fbplatform.ml.goals</code> first.</Callout> : <>
        <Tabs tabs={["Classification", "Importance & SHAP", "Calibration & residuals", "Clustering", "Model comparison"]} value={tab} onChange={setTab} id="lml" />
        <div className="pt-6">
          {tab === "Classification" && <>
            <Row className="mb-4"><SelectField label="Model" value={mm} onChange={setModel} options={models} /><Toggle label="Show row percentages" value={norm} onChange={setNorm} /></Row>
            <Charts specs={[{ id: "ml.confusion", fixed: { model: mm, norm } }]} />
            <Row className="mb-4"><Segmented label="Outcome for the curves (one-vs-rest)" value={cls} onChange={(v) => setCls(Number(v))} options={CLS} /></Row>
            <Charts specs={[{ id: "ml.roc", fixed: { cls } }, { id: "ml.pr", fixed: { cls } }]} />
          </>}
          {tab === "Importance & SHAP" && <>
            <Charts specs={[{ id: "ml.imp_perm" }, { id: "ml.imp_gain" }, { id: "ml.shap_bar" }]} />
            <Row className="mb-4"><Segmented label="Outcome for the beeswarm" value={cls2} onChange={(v) => setCls2(Number(v))} options={CLS} />{feats.length > 0 && <SelectField label="Dependence plot feature" value={fe} onChange={setFeat} options={feats} />}</Row>
            <Charts specs={[{ id: "ml.shap_swarm", fixed: { cls: cls2 } }, ...(feats.length ? [{ id: "ml.shap_dep", fixed: { feature: fe, cls: cls2 } }] : [])]} />
          </>}
          {tab === "Calibration & residuals" && <>
            <Row className="mb-4"><SelectField label="Model" value={mm2} onChange={setM2} options={models} /><SelectField label="Outcome" value={k2} onChange={(v) => setK2(Number(v))} options={CLS} /></Row>
            <Charts specs={[{ id: "ml.calib", fixed: { model: mm2, cls: k2 } }, { id: "ml.goals_avp" }, { id: "ml.resid" }]} />
          </>}
          {tab === "Clustering" && <>
            <Charts specs={[{ id: "ml.team_clusters" }, { id: "ml.sil" }, { id: "ml.dendro" }]} />
            <Row className="mb-4"><Segmented label="Players: position group" value={pos} onChange={setPos} options={["Forward", "Midfielder", "Defender"]} /></Row>
            <Charts specs={[{ id: "ml.player_clusters", fixed: { position: pos } }]} />
          </>}
          {tab === "Model comparison" && <>
            <Row className="mb-4"><Segmented label="Outcome-model metric" value={met} onChange={setMet} options={["log_loss", "accuracy", "f1_macro", "roc_auc_ovr"]} /></Row><Charts specs={[{ id: "ml.cmp", fixed: { metric: met } }]} />
            <Row className="mb-4"><Segmented label="Goal-model metric" value={gm} onChange={setGm} options={["poisson_deviance", "mae_team_goals", "rmse_team_goals", "mae_total_goals"]} /></Row><Charts specs={[{ id: "ml.gcmp", fixed: { metric: gm } }]} />
          </>}
        </div></>}
    </div>
  );
}
