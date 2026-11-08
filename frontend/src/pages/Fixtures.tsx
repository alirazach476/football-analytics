import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useLookups } from "../api";
import { HUB_THEME, themeFor } from "../theme/editions";
import { useThemeOverride } from "../theme/useTheme";
import { Callout, PageHeader, Skeleton } from "../components/ui";
import { MultiSelect, Row, Segmented } from "../components/controls";
import FixtureCard from "../components/match/FixtureCard";
import { MatchRow, compLabel, editionLabel } from "../components/match/matchUtils";

const STATUSES: [string, string][] = [["all", "All"], ["played", "Full time"], ["upcoming", "Coming soon"], ["extra_time", "Extra time"], ["penalties", "Penalties"]];
const PAGE = 120;

export default function Fixtures() {
  const { data: lk } = useLookups();
  const [q, setQ] = useState(""); const [dq, setDq] = useState(""); const [comps, setComps] = useState<string[]>([]); const [seasons, setSeasons] = useState<string[]>([]); const [stages, setStages] = useState<string[]>([]);
  const [status, setStatus] = useState("played"); const [order, setOrder] = useState("desc"); const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  useEffect(() => { const t = setTimeout(() => setDq(q), 250); return () => clearTimeout(t); }, [q]);
  const filters = useMemo(() => ({ competitions: comps, seasons, stages, date_from: from || null, date_to: to || null }), [comps, seasons, stages, from, to]);
  const res = useInfiniteQuery({
    queryKey: ["fixtures", filters, dq, status, order], initialPageParam: 0,
    queryFn: async ({ pageParam }) => { const r = await fetch("/api/fixtures", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filters, q: dq, status, order, offset: pageParam, limit: PAGE }) }); if (!r.ok) throw new Error(r.statusText); return (await r.json()) as { total: number; rows: MatchRow[] }; },
    getNextPageParam: (last, all) => { const n = all.reduce((a, p) => a + p.rows.length, 0); return n < last.total ? n : undefined; }, placeholderData: (p) => p,
  });
  const rows = res.data?.pages.flatMap((p) => p.rows) ?? []; const total = res.data?.pages[0]?.total ?? 0;
  // theme: one edition selected -> its logo theme; one competition -> its flagship's theme
  useThemeOverride(seasons.length === 1 ? seasons[0] : comps.length === 1 ? HUB_THEME[comps[0]] : null);
  const groups = useMemo(() => { const g = new Map<string, MatchRow[]>(); rows.forEach((m) => g.set(m.season_id, [...(g.get(m.season_id) ?? []), m])); return Array.from(g); }, [rows]);
  const seasonOpts = (lk?.seasons ?? []).filter((s) => !comps.length || comps.includes(s.competition)).map((s) => s.seasonId);
  return (
    <div>
      <PageHeader eyebrow="Match center" title="Fixtures & results" subtitle="Every match in the data, played or coming soon. Open one for its full Match Center." />
      <div className="card mb-6 space-y-4 p-4">
        <Row>
          <label className="block min-w-[14rem] flex-1"><span className="label">Search team</span><div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--c-muted)" }} /><input className="field pl-8" placeholder="e.g. Argentina" value={q} onChange={(e) => setQ(e.target.value)} /></div></label>
          <MultiSelect label="Competition" value={comps} onChange={(v) => { setComps(v); setSeasons([]); }} options={(lk?.competitions ?? []).map((c) => [c.id, c.label] as [string, string])} searchable={false} />
          <MultiSelect label="Edition" value={seasons} onChange={setSeasons} options={seasonOpts} />
          <MultiSelect label="Stage" value={stages} onChange={setStages} options={lk?.stages ?? []} searchable={false} />
          <label className="block"><span className="label">From</span><input type="date" className="field" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="block"><span className="label">To</span><input type="date" className="field" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        </Row>
        <Row><Segmented label="Status" value={status} onChange={setStatus} options={STATUSES} /><Segmented label="Sort by date" value={order} onChange={setOrder} options={[["desc", "Newest first"], ["asc", "Oldest first"]]} /></Row>
      </div>
      {status === "played" && <Callout tone="soon" className="mb-4">Showing played matches first. Scheduled fixtures stay in the data: choose <b>Coming soon</b> in the status filter to see them.</Callout>}
      <p className="mb-4 text-sm" style={{ color: "var(--c-muted)" }}>{total.toLocaleString()} match{total === 1 ? "" : "es"}{rows.length < total ? ` · showing ${rows.length}` : ""}</p>
      {res.isError && <Callout tone="warn" title="Could not load fixtures">{(res.error as Error).message}</Callout>}
      {res.isLoading ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={150} />)}</div>
        : rows.length === 0 ? <Callout tone="info" title="No matches">No match fits these filters. Try removing a filter.</Callout>
        : groups.map(([season, list]) => { const t = themeFor(season); return (
          <section key={season} className="mb-8">
            <h2 className="mb-3 flex items-center gap-3 font-display text-lg font-extrabold uppercase tracking-wide"><img src={t.logo} alt="" className="h-9 w-9 rounded-lg bg-white p-1 object-contain" />{compLabel(list[0])} {editionLabel(season)}<span className="text-xs font-semibold normal-case tracking-normal" style={{ color: "var(--c-muted)" }}>{list.length} shown</span></h2>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{list.map((m) => <FixtureCard key={m.match_key} m={m} showComp={false} />)}</div>
          </section>); })}
      {res.hasNextPage && <div className="mt-4 text-center"><button className="btn btn-primary" disabled={res.isFetchingNextPage} onClick={() => res.fetchNextPage()}>{res.isFetchingNextPage ? "Loading…" : "Load more matches"}</button></div>}
    </div>
  );
}
