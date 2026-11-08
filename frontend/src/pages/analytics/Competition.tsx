import { useMemo, useState } from "react";
import { useApiQuery } from "../../api";
import { KpiCard, PageHeader } from "../../components/ui";
import { SelectField } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import { Block, COMP_OPTS, ComingSoonNote, Loading, T, pick, useTable } from "./kit";

const METRICS: [string, string][] = [["goals_per_match", "Goals per match"], ["draw_pct", "Draw %"], ["avg_attendance", "Average attendance"], ["matches_beyond_90", "Matches beyond 90 min (count)"]];

export default function Competition() {
  const [comp, setComp] = useState("WC"); const name = COMP_OPTS.find(([id]) => id === comp)![1];
  const ed = useTable("edition_table", { comp }); const rec = useApiQuery<any>("records", { comp }).data;
  const played = useMemo(() => ed.rows.filter((r) => r.matches_played > 0), [ed.rows]);
  const mp = played.reduce((a, r) => a + r.matches_played, 0);
  return (
    <div>
      <PageHeader title={`Competition analysis: ${name}`} right={<SelectField label="Competition" value={comp} onChange={setComp} options={COMP_OPTS} />} />
      <ComingSoonNote n={ed.rows.reduce((a, r) => a + (r.matches_coming_soon ?? 0), 0)} />
      {ed.isLoading ? <Loading /> : <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Editions played" value={played.length} /><KpiCard label="Matches played" value={mp} />
        <KpiCard label="Goals per match" value={mp ? (played.reduce((a, r) => a + r.total_goals, 0) / mp).toFixed(2) : "–"} />
        <KpiCard label="Draw share" value={mp ? `${(played.reduce((a, r) => a + r.draw_pct * r.matches_played, 0) / mp).toFixed(1)}%` : "–"} /></div>}
      <Block title="Edition comparison" hint="Measure per match, so editions of different size are comparable.">
        <ChartSection key={comp + "m"} spec={{ id: "an.edition_metric", fixed: { comp }, params: [{ key: "metric", label: "Measure", type: "segmented", options: METRICS, default: "goals_per_match" }] }} />
      </Block>
      <Block title="Match outcomes by edition"><ChartSection key={comp + "o"} spec={{ id: "an.outcomes", fixed: { comp } }} /></Block>
      <Block title="Tournament records">
        <T t={pick(ed.table, ["season_id", "teams", "matches_played", "total_goals", "goals_per_match", "champion", "runner_up", "tournament_status"])} filename={`${comp}_editions`} searchable={false} pageSize={30} />
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div><h3 className="mb-2 font-semibold">Highest-scoring matches</h3><T t={rec?.highest_scoring} searchable={false} filename="highest_scoring" /></div>
          <div><h3 className="mb-2 font-semibold">Biggest winning margins</h3><T t={rec?.biggest_margin} searchable={false} filename="biggest_margin" /></div>
        </div>
        <h3 className="mb-2 mt-6 font-semibold">Top scorers in this competition <span className="text-xs font-normal" style={{ color: "var(--c-muted)" }}>(goals linked to a player; Nations League scorers are not linked)</span></h3>
        <T t={rec?.top_scorers} filename="top_scorers" />
      </Block>
      <Block title="Goals by minute band"><ChartSection key={comp + "g"} spec={{ id: "an.goal_minutes", fixed: { comp } }} /></Block>
    </div>
  );
}
