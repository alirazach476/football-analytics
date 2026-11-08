import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Callout, PageHeader, Tabs } from "../../components/ui";
import DataTable from "../../components/DataTable";
import { Charts } from "./labkit";

export default function LabEngineering() {
  const [tab, setTab] = useState("Layer record counts");
  const eng = useQuery({ queryKey: ["labeng"], queryFn: async () => (await fetch("/api/lab/engineering")).json() as Promise<any>, staleTime: 300_000 }).data;
  return (
    <div>
      <PageHeader eyebrow="Visualization lab" title="Data-engineering visualisations" subtitle="Pipeline health, completeness and coverage. Missing values are never shown as zero: genuine zeros (e.g. attendance 0 = closed doors) are reported separately." />
      <Tabs tabs={["Layer record counts", "Completeness & missing values", "Duplicates", "Pipeline runs", "Freshness", "Source coverage", "Quality trends"]} value={tab} onChange={setTab} id="le" />
      <div className="pt-6">
        {tab === "Layer record counts" && <><Charts specs={[{ id: "eng.layers" }]} /><DataTable table={eng?.rawFiles} filename="raw_files" searchable={false} />
          <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Registered raw source files (Bronze) by source; UEFA Champions League files are flagged and excluded from processing, never deleted.</p></>}
        {tab === "Completeness & missing values" && <>
          {eng && <Callout tone="info" className="mb-5">Played matches only ({eng.playedMatches.toLocaleString()}). The {eng.comingSoon} 'Coming soon' fixtures are excluded here: their missing referee, attendance and score are expected, not data gaps.</Callout>}
          <Charts specs={[{ id: "eng.miss_matches" }, { id: "eng.miss_players" }, { id: "eng.complete" }]} /></>}
        {tab === "Duplicates" && <Charts specs={[{ id: "eng.dups" }]} />}
        {tab === "Pipeline runs" && <><Charts specs={[{ id: "eng.durations" }, { id: "eng.failures" }]} />
          <details className="card p-4"><summary className="cursor-pointer font-semibold">Failed attempts ({eng?.failed?.total ?? 0}) with their error text</summary><div className="mt-3"><DataTable table={eng?.failed} filename="failed_attempts" empty="No failed attempts." /></div></details></>}
        {tab === "Freshness" && <Charts specs={[{ id: "eng.fresh" }]} />}
        {tab === "Source coverage" && <Charts specs={[{ id: "eng.coverage" }]} />}
        {tab === "Quality trends" && <Charts specs={[{ id: "eng.dq" }]} />}
      </div>
    </div>
  );
}
