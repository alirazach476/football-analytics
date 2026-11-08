import { useMemo, useState } from "react";
import { useApiQuery } from "../../api";
import { Callout, KpiCard, PageHeader, Tabs } from "../../components/ui";
import { Toggle } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import QuickPlot from "../../components/QuickPlot";
import { Block, Loading, T, pick, useTable } from "./kit";

export default function Engineering() {
  const [tab, setTab] = useState("Pipeline runs"); const [only, setOnly] = useState(false);
  const fr = useTable("freshness"); const dq = useApiQuery<any>("data_quality_score").data;
  const ps = useTable("pipeline_summary"); const runs = useTable("pipeline_runs"); const ing = useTable("ingestion_status"); const d = useTable("dq_results", { only_failed: only });
  const cov = useTable("coverage_report"); const dup = useTable("duplicate_checks"); const db = useTable("db_stats");
  const dqSummary = useMemo(() => { const m = new Map<string, number>(); d.rows.forEach((r) => m.set(`${r.layer}|${r.status}`, (m.get(`${r.layer}|${r.status}`) ?? 0) + 1)); return Array.from(m, ([k, v]) => { const [layer, status] = k.split("|"); return { layer, status, v }; }); }, [d.rows]);
  const sortedDb = useMemo(() => [...db.rows].sort((a, b) => a.rows - b.rows), [db.rows]);
  return (
    <div>
      <PageHeader title="Data engineering: pipeline health and data quality" />
      {fr.isLoading ? <Loading /> : <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-4">{fr.rows.map((r) => <KpiCard key={r.item} label={r.item} value={String(r.value ?? "n/a").slice(0, 19)} />)}</div>}
      <div className="mb-6 max-w-xs"><KpiCard label="Data quality score" value={dq?.score == null ? "n/a" : `${Math.round(dq.score)}%`} hint="share of automated checks that passed in the latest runs; rule compliance, not completeness" /></div>
      <Tabs tabs={["Pipeline runs", "Ingestion", "Data quality checks", "Coverage & missing data", "Duplicates", "Database"]} value={tab} onChange={setTab} id="eng" />
      <div className="pt-6">
        {tab === "Pipeline runs" && <>
          <Block title="Recent runs" hint="One run = bronze → silver → validation → warehouse → dbt → coverage."><T t={ps.table} filename="pipeline_summary" searchable={false} /></Block>
          <ChartSection spec={{ id: "eng.durations" }} />
          <Block title="Step history"><T t={runs.table} filename="pipeline_runs" pageSize={15} /><p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>'skipped' = the step's input had not changed (idempotent re-run). Failed attempts are retried and every attempt is logged.</p></Block>
        </>}
        {tab === "Ingestion" && <>
          <T t={ing.table} filename="ingestion_status" searchable={false} />
          <div className="mt-5"><QuickPlot data={[{ type: "bar", x: ing.rows.map((r) => r.source), y: ing.rows.map((r) => r.files), marker: { color: "#2a78d6" } }]} layout={{ title: { text: "Registered source files (Bronze) by source" } }}
            caption="Every raw file is registered with SHA-256 and a version; originals are never modified. UEFA Champions League files are flagged and excluded from all processing (kept on disk, not deleted)." /></div>
        </>}
        {tab === "Data quality checks" && <>
          <div className="mb-3"><Toggle label="Only failed checks" value={only} onChange={setOnly} /></div>
          <T t={d.table} filename="dq_results" pageSize={15} />
          {only && d.rows.length === 0 && <Callout tone="info" className="mt-3">No failed checks in the stored history.</Callout>}
          <div className="mt-5"><QuickPlot data={["pass", "fail"].map((s) => ({ type: "bar", name: s, x: dqSummary.filter((r) => r.status === s).map((r) => r.layer), y: dqSummary.filter((r) => r.status === s).map((r) => r.v), marker: { color: s === "pass" ? "#009E73" : "#D55E00" } }))}
            layout={{ barmode: "stack", title: { text: "Checks by layer and status" } }} /></div>
          <ChartSection spec={{ id: "eng.dq" }} />
        </>}
        {tab === "Coverage & missing data" && <>
          <ChartSection spec={{ id: "eng.coverage" }} />
          <T t={pick(cov.table, ["season_id", "expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon", "coverage_flag"])} filename="coverage" searchable={false} pageSize={30} />
          <p className="mb-6 mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Expected matches come from format arithmetic and are unverified. Gaps are source limits: no minute-level events/lineups for Nations League group matches, no man-of-the-match for Copa 2001–2007, coordinates only for StatsBomb/Wyscout matches.</p>
          <ChartSection spec={{ id: "eng.miss_matches" }} /><ChartSection spec={{ id: "eng.miss_players" }} /><ChartSection spec={{ id: "eng.complete" }} />
        </>}
        {tab === "Duplicates" && <><T t={dup.table} filename="duplicates" searchable={false} />
          <p className="mb-5 mt-2 text-xs" style={{ color: "var(--c-muted)" }}>'Merged' counts are identities unified by the documented entity-resolution rules (same name and birth date, or name containment + same national team + never in one line-up).</p><ChartSection spec={{ id: "eng.dups" }} /></>}
        {tab === "Database" && <><T t={db.table} filename="db_stats" searchable={false} pageSize={40} />
          <div className="mt-5"><QuickPlot height={Math.max(360, sortedDb.length * 22 + 100)} data={[{ type: "bar", orientation: "h", y: sortedDb.map((r) => r.table), x: sortedDb.map((r) => r.rows), marker: { color: "#2a78d6" } }]} layout={{ title: { text: "Rows per warehouse table (log scale)" }, xaxis: { type: "log" }, margin: { l: 170, r: 20, t: 56, b: 50 } }} /></div></>}
      </div>
    </div>
  );
}
