import { useState } from "react";
import { Callout, Tabs } from "../../components/ui";
import { SelectField, Toggle } from "../../components/controls";
import { ChartSpec } from "../../components/ChartSection";
import { Charts, LabPage, useLab, useShared } from "./labkit";

const MEASURES: [string, string][] = [["total_goals", "Goals"], ["matches_played", "Matches"], ["goals_per_match", "Goals per match"]];
const METRICS: [string, string][] = [["goals_per_match", "Goals per match"], ["draw_pct", "Draw share (%)"], ["avg_attendance", "Average attendance"], ["shootout_rate", "Shoot-outs per 100 matches"], ["beyond90_rate", "Matches beyond 90 min (%)"]];

export default function LabCompetitions() {
  const lab = useLab(); const [tab, setTab] = useState("History"); const [sh, setSh] = useShared(); const [reg, setReg] = useState(true);
  const eds = lab.data?.editions ?? []; const sel: string | undefined = sh.season_sel; const season = sel && eds.includes(sel) ? sel : eds[eds.length - 1];
  const shared = { season };
  const SeasonPick = () => <div className="mb-4 max-w-xs">{eds.length ? <SelectField label="Edition" value={season} onChange={(v) => setSh({ season_sel: v })} options={eds} /> : <Callout tone="info">No edition matches the current filters.</Callout>}</div>;
  const hist: ChartSpec = { id: "comp.history", params: [{ key: "measure", label: "Measure", type: "segmented", options: MEASURES, default: "goals_per_match" }], cross: { field: "customdata0", set: "season_sel" }, hint: "Click a bar or point to select that edition: the detail tabs (progression, standings, bracket) follow your selection." };
  return (
    <LabPage title="Competition visualisations" sample={lab.data?.sample} caption="Played matches only; upcoming fixtures appear in brackets as 'Coming soon'. Edition-level charts use whole editions (competition/edition filters apply; date, stage and team filters apply to match-level charts).">
      <Tabs tabs={["History", "Champions", "Edition comparison", "Progression & groups", "Knockout bracket", "Goal distributions"]} value={tab} onChange={setTab} id="lc" />
      <div className="pt-6">
        {tab === "History" && <>
          <Charts specs={[hist]} shared={sh} setShared={setSh} />
          {sel && <Callout tone="info" className="mb-4"><span>Selected edition: <b>{sel}</b> (used in the detail tabs) </span><button className="btn ml-3 !py-0.5" onClick={() => setSh({ season_sel: undefined })}>Clear selection</button></Callout>}
        </>}
        {tab === "Champions" && <Charts specs={[{ id: "comp.champions" }, { id: "comp.titles" }]} />}
        {tab === "Edition comparison" && <Charts specs={[{ id: "comp.compare", params: [{ key: "metric", label: "Measure", type: "select", options: METRICS, default: "goals_per_match" }] }, { id: "comp.compare_heat" }]} />}
        {tab === "Progression & groups" && <><SeasonPick />{season && <Charts specs={[{ id: "comp.funnel", shared: ["season"] }, { id: "comp.groups", shared: ["season"] }]} shared={shared} />}</>}
        {tab === "Knockout bracket" && <><SeasonPick />{season && <Charts specs={[{ id: "comp.bracket", shared: ["season"] }]} shared={shared} />}</>}
        {tab === "Goal distributions" && <>
          <div className="mb-4"><Toggle label="Regulation time only (exclude extra-time goals)" value={reg} onChange={setReg} /></div>
          <Charts specs={[{ id: "comp.gdist", fixed: { regulation: reg } }, { id: "comp.gminutes" }]} />
        </>}
      </div>
    </LabPage>
  );
}
