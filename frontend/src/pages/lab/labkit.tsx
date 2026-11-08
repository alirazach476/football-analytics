import { ReactNode, useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filters, saveBlob } from "../../api";
import { useFilters } from "../../state/filters";
import FilterBar from "../../components/FilterBar";
import ChartSection, { ChartSpec, Shared } from "../../components/ChartSection";
import { PageHeader } from "../../components/ui";

export interface LabLists { teams: string[]; sample: { played: number; total: number; playerRows: number; players: number }; players: string[]; radarPlayers: string[]; matches?: { key: number; label: string; played: boolean; home: string; away: string; fixtureDetail: string | null; season: string }[]; shotTeams?: string[]; editions: string[] }

export function useLab(extra: Record<string, any> = {}) {
  const { filters } = useFilters();
  return useQuery({ queryKey: ["lab", filters, extra], queryFn: async () => {
    const r = await fetch("/api/lab/lists", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filters, ...extra }) });
    if (!r.ok) throw new Error(r.statusText); return (await r.json()) as LabLists;
  }, placeholderData: (p) => p, staleTime: 60_000 });
}

export function LabPage({ title, caption, teams = true, stages = true, download = "matches", sample, children }: { title: string; caption: ReactNode; teams?: boolean; stages?: boolean; download?: "matches" | "players"; sample?: LabLists["sample"]; children: ReactNode }) {
  return (
    <div>
      <PageHeader eyebrow="Visualization lab" title={title} subtitle={caption} />
      <FilterBar teams={teams} stages={stages} download={download} />
      {sample && <p className="mb-5 text-xs" style={{ color: "var(--c-muted)" }}>{download === "players" ? <><b>{sample.playerRows.toLocaleString()}</b> player-tournament rows in the current selection · <b>{sample.players.toLocaleString()}</b> players.</> :
        <><b>{sample.played.toLocaleString()}</b> of {sample.total.toLocaleString()} matches in the current selection (played matches only; 'Coming soon' fixtures are never part of statistics).</>}</p>}
      {children}
    </div>
  );
}

export function useShared(init: Shared = {}): [Shared, (p: Shared) => void] {
  const [s, setS] = useState<Shared>(init);
  return [s, useCallback((p: Shared) => setS((x) => ({ ...x, ...p })), [])];
}

export function Charts({ specs, shared, setShared }: { specs: ChartSpec[]; shared?: Shared; setShared?: (p: Shared) => void }) {
  return <>{specs.map((sp, i) => <ChartSection key={`${sp.id}-${i}`} spec={sp} shared={shared} setShared={setShared} />)}</>;
}

export function StaticImage({ id, filters, params }: { id: string; filters: Filters; params: Record<string, any> }) {
  const q = useQuery({ queryKey: ["static", id, filters, params], queryFn: async () => {
    const r = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, filters, params, format: "png" }) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error); return r.blob();
  }, staleTime: Infinity });
  if (q.isError) return <p className="text-sm text-red-500">{(q.error as Error).message}</p>;
  if (!q.data) return <div className="skeleton h-64" />;
  const url = URL.createObjectURL(q.data);
  return <figure className="chart-card mb-6 p-3"><img src={url} alt="Matplotlib/Seaborn version of the chart" className="mx-auto max-w-full" /><button className="btn mt-2" onClick={() => saveBlob(q.data!, `${id}.png`)}>Download PNG</button></figure>;
}
