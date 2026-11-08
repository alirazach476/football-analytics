import { useMemo, useState } from "react";
import { useApiQuery } from "../../api";
import { Callout, KpiCard, PageHeader } from "../../components/ui";
import { SelectField } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import { Block, ComingSoonNote, Loading, T, sign, useTable } from "./kit";

const MEASURES = ["matches", "win_pct", "points_per_match", "goals_for", "goals_against", "goal_diff", "clean_sheets"];

export default function Teams() {
  const names = useApiQuery<string[]>("team_names").data ?? [];
  const [team, setTeam] = useState("Argentina"); const [other, setOther] = useState("France");
  const s = useTable("team_summary", { team }).rows[0]; const so = useTable("team_summary", { team: other }).rows[0];
  const ed = useTable("team_by_edition", { team }); const res = useTable("team_results", { team }); const up = useTable("team_upcoming", { team });
  const h2h = useTable("head_to_head_table", { a: team, b: other });
  const cmp = useMemo(() => s && so ? { columns: ["measure", team, other], rows: MEASURES.map((m) => ({ measure: m, [team]: s[m], [other]: so[m] })), total: MEASURES.length } : undefined, [s, so, team, other]);
  const none = s && Number(s.matches) === 0;
  return (
    <div>
      <PageHeader title="Team analytics" subtitle="Records cover only matches in the four collected competitions (no friendlies or qualifiers). Result = recorded score (extra time included, shoot-outs excluded)."
        right={<SelectField label="Team" value={team} onChange={setTeam} options={names} />} />
      {!s ? <Loading /> : none ? <Callout tone="info">No played matches for this team yet.</Callout> : <>
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <KpiCard label="Matches" value={s.matches} /><KpiCard label="W-D-L" value={`${s.wins}-${s.draws}-${s.losses}`} /><KpiCard label="Win %" value={`${s.win_pct}%`} />
          <KpiCard label="Goals for/against" value={`${s.goals_for}/${s.goals_against}`} /><KpiCard label="Goal difference" value={sign(s.goal_diff)} /><KpiCard label="Clean sheets" value={s.clean_sheets} /></div>
        <Block title="Performance by edition" hint="Two measures on different scales → two charts, never a shared axis.">
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartSection key={team + "a"} spec={{ id: "an.team_edition", fixed: { team, measure: "goals_for_per_match" }, height: 340 }} />
            <ChartSection key={team + "b"} spec={{ id: "an.team_edition", fixed: { team, measure: "win_pct" }, height: 340 }} />
          </div>
          <T t={ed.table} filename={`${team}_by_edition`} pageSize={30} searchable={false} />
        </Block>
        <Block title="Historical results"><T t={res.table} filename={`${team}_results`} pageSize={15} /></Block>
        <Block title="Scoring trend"><ChartSection key={team + "t"} spec={{ id: "an.team_trend", fixed: { team } }} /></Block>
      </>}
      {up.rows.length > 0 && <Block title="Coming soon"><ComingSoonNote n={up.rows.length} /><T t={up.table} filename={`${team}_upcoming`} searchable={false} /></Block>}
      <Block title="Compare with another team">
        <div className="mb-3 max-w-xs"><SelectField label="Compare with" value={other} onChange={setOther} options={names.filter((n) => n !== team)} /></div>
        {cmp ? <T t={cmp} searchable={false} filename="team_comparison" /> : <Loading />}
        <p className="mb-2 mt-5 font-semibold">Head-to-head meetings: {h2h.rows.length}</p>
        {h2h.rows.length > 0 && <T t={h2h.table} filename="head_to_head" />}
        <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Meetings span different competitions, stages and eras: they are context, not a prediction.</p>
      </Block>
    </div>
  );
}
