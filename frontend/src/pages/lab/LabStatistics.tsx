import { useState } from "react";
import { Tabs } from "../../components/ui";
import { Row, Segmented, SelectField, Toggle } from "../../components/controls";
import { useFilters } from "../../state/filters";
import { Charts, LabPage, StaticImage, useLab } from "./labkit";

const COLS: [string, string][] = [["gf_pm", "Goals for / match"], ["ga_pm", "Goals against / match"], ["ppm", "Points / match"], ["win_pct", "Win %"], ["cs_pct", "Clean sheets %"]];
const VARS: [string, string][] = [["goals90", "Goals in regulation time"], ["goals_total", "Goals incl. extra time"], ["margin", "Goal margin (|home − away|)"]];

export default function LabStatistics() {
  const lab = useLab(); const { filters } = useFilters(); const [tab, setTab] = useState("Correlations");
  const [method, setMethod] = useState("spearman"); const [v1, setV1] = useState("goals90"); const [v2, setV2] = useState("goals90"); const [by, setBy] = useState("stage_name");
  const [x, setX] = useState("gf_pm"); const [y, setY] = useState("ppm"); const [kind, setKind] = useState("ratio"); const [stat, setStat] = useState(false);
  const yy = y === x ? COLS.find(([k]) => k !== x)![0] : y;
  return (
    <LabPage title="Statistical visualisations" teams={false} sample={lab.data?.sample} caption="Association is not causation. Goal counts are discrete and over-dispersed, so rank-based and count-model tools are used; every chart shows its sample size.">
      <Tabs tabs={["Correlations", "Distributions", "Box & violin", "Scatter & regression", "Confidence intervals", "Hypothesis tests", "Regression diagnostics"]} value={tab} onChange={setTab} id="ls" />
      <div className="pt-6">
        {tab === "Correlations" && <><Row className="mb-4"><Segmented label="Method" value={method} onChange={setMethod} options={["spearman", "pearson"]} /></Row><Charts specs={[{ id: "stat.corr", fixed: { method } }]} /></>}
        {tab === "Distributions" && <><Row className="mb-4"><Segmented label="Variable" value={v1} onChange={setV1} options={VARS} /></Row><Charts specs={[{ id: "stat.dist", fixed: { var: v1 } }]} /></>}
        {tab === "Box & violin" && <><Row className="mb-4"><Segmented label="Variable" value={v2} onChange={setV2} options={VARS.filter(([k]) => k !== "goals_total")} />
          <Segmented label="Group by" value={by} onChange={setBy} options={[["stage_name", "Stage"], ["competition_id", "Competition"]]} /></Row>
          <Charts specs={[{ id: "stat.box", fixed: { var: v2, by } }, { id: "stat.violin" }]} /></>}
        {tab === "Scatter & regression" && <><Row className="mb-4"><SelectField label="X" value={x} onChange={setX} options={COLS} /><SelectField label="Y" value={yy} onChange={setY} options={COLS.filter(([k]) => k !== x)} /></Row>
          <Charts specs={[{ id: "stat.scatter", fixed: { x, y: yy } }]} /></>}
        {tab === "Confidence intervals" && <><Row className="mb-4"><Segmented label="Kind of estimate (each kind has its own scale)" value={kind} onChange={setKind} options={["ratio", "difference", "proportion"]} /></Row><Charts specs={[{ id: "stat.forest", fixed: { kind } }]} /></>}
        {tab === "Hypothesis tests" && <Charts specs={[{ id: "stat.hyp" }]} />}
        {tab === "Regression diagnostics" && <><Charts specs={[{ id: "stat.diag" }]} />
          <div className="mb-3"><Toggle label="Show the Matplotlib/Seaborn version" value={stat} onChange={setStat} /></div>
          {stat && <StaticImage id="stat.diag" filters={filters} params={{}} />}</>}
      </div>
    </LabPage>
  );
}
