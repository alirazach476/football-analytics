import { useMemo, useState } from "react";
import { Callout, KpiCard, PageHeader, Tabs } from "../../components/ui";
import { SearchBox, Segmented, SelectField } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import { Link } from "react-router-dom";
import CountryFlag from "../../components/CountryFlag";
import { Block, Loading, T, n0, useTable } from "./kit";

const sum = (rows: any[], k: string) => rows.reduce((a, r) => a + (Number(r[k]) || 0), 0);

function PlayerPick({ label, term, setTerm, value, setValue }: { label: string; term: string; setTerm: (v: string) => void; value?: string; setValue: (v: string) => void }) {
  const res = useTable("player_search", { term }, term.length >= 2);
  const opts: [string, string][] = res.rows.map((r) => [String(r.player_key), `${r.full_name} (${r.nationality || "nationality n/a"})`]);
  const cur = value && opts.some(([k]) => k === value) ? value : opts[0]?.[0];
  return <div className="space-y-2"><SearchBox label={label} value={term} onChange={setTerm} />{opts.length > 0 ? <SelectField label="Pick" value={cur} onChange={setValue} options={opts} /> : <p className="text-sm" style={{ color: "var(--c-muted)" }}>No player found. Try another spelling.</p>}<input type="hidden" value={cur ?? ""} readOnly /></div>;
}

export default function Players() {
  const [tab, setTab] = useState("Player profile");
  const [term, setTerm] = useState("Messi"); const [pk, setPk] = useState<string>();
  const res = useTable("player_search", { term }, term.length >= 2); const key = pk && res.rows.some((r) => String(r.player_key) === pk) ? pk : res.rows[0] ? String(res.rows[0].player_key) : undefined;
  const prof = useTable("player_profile", { player_key: Number(key) }, !!key).rows[0]; const by = useTable("player_by_edition", { player_key: Number(key) }, !!key); const aw = useTable("player_awards", { player_key: Number(key) }, !!key);
  const [metric, setMetric] = useState("goals"); const top = useTable("top_players", { metric, limit: 25 });
  const [t1, setT1] = useState("Ronaldo"); const [t2, setT2] = useState("Messi"); const [p1, setP1] = useState<string>(); const [p2, setP2] = useState<string>();
  const r1 = useTable("player_search", { term: t1 }, t1.length >= 2).rows, r2 = useTable("player_search", { term: t2 }, t2.length >= 2).rows;
  const k1 = p1 && r1.some((r) => String(r.player_key) === p1) ? p1 : r1[0] && String(r1[0].player_key), k2 = p2 && r2.some((r) => String(r.player_key) === p2) ? p2 : r2[0] && String(r2[0].player_key);
  const e1 = useTable("player_by_edition", { player_key: Number(k1) }, !!k1).rows, e2 = useTable("player_by_edition", { player_key: Number(k2) }, !!k2).rows;
  const totals = useMemo(() => {
    if (!k1 || !k2) return undefined;
    const rows = [[r1.find((r) => String(r.player_key) === k1)?.full_name, e1], [r2.find((r) => String(r.player_key) === k2)?.full_name, e2]].map(([n, e]: any) => ({ player: n, appearances: sum(e, "appearances"), goals: sum(e, "goals"), assists: sum(e, "assists"), minutes_played: sum(e, "minutes_played"),
      goals_per_appearance: sum(e, "appearances") ? Math.round((sum(e, "goals") / sum(e, "appearances")) * 1000) / 1000 : null }));
    return { columns: Object.keys(rows[0]), rows, total: 2 };
  }, [k1, k2, e1, e2, r1, r2]);
  return (
    <div>
      <PageHeader2 />
      <Callout tone="warn" className="mb-5">Numbers cover only the collected competitions (not careers). Goals are goals linked to a player id: Nations League scorers are not linked, and assists exist only where the sources record them (mainly StatsBomb-covered editions). Minutes are approximate for Wikipedia-based editions.</Callout>
      <Tabs tabs={["Player profile", "Top lists", "Compare players"]} value={tab} onChange={setTab} id="pl" />
      <div className="pt-6">
        {tab === "Player profile" && <>
          <div className="mb-5 max-w-xl"><SearchBox label="Search a player (name contains)" value={term} onChange={setTerm} />
            {res.rows.length > 0 && <div className="mt-3"><SelectField label="Player" value={key} onChange={setPk} options={res.rows.map((r) => [String(r.player_key), `${r.full_name} (${r.nationality || "nationality n/a"})`] as [string, string])} /></div>}</div>
          {!res.rows.length ? <Callout tone="info">No player found. Try another spelling.</Callout> : !prof ? <Loading /> : <>
            <div className="mb-4 flex flex-wrap items-center gap-3">{(prof.nationality ?? res.rows.find((r) => String(r.player_key) === key)?.plays_for) && <CountryFlag country={prof.nationality ?? res.rows.find((r) => String(r.player_key) === key)?.plays_for} size={40} />}<h2 className="font-display text-2xl font-bold">{prof.full_name}</h2><Link to={`/player/${key}`} className="btn btn-primary">Open full player page</Link></div>
            <div className="mb-3 grid grid-cols-2 gap-4 md:grid-cols-5">
              <KpiCard label="Appearances" value={sum(by.rows, "appearances")} /><KpiCard label="Goals" value={sum(by.rows, "goals")} /><KpiCard label="Assists (where recorded)" value={sum(by.rows, "assists")} />
              <KpiCard label="Minutes (known)" value={n0(Math.round(sum(by.rows, "minutes_played")))} /><KpiCard label="Tournaments" value={new Set(by.rows.map((r) => r.season_id)).size} /></div>
            <p className="mb-5 text-xs" style={{ color: "var(--c-muted)" }}>Position (where known): {prof.primary_position || "n/a"} · Date of birth: {prof.date_of_birth || "n/a"} · merged from {prof.n_source_ids} source id(s)</p>
            <ChartSection key={key} spec={{ id: "an.player_edition", fixed: { player_key: Number(key) } }} />
            <T t={by.table} filename="player_by_edition" searchable={false} />
            {aw.rows.length > 0 && <Block title="Individual awards" hint="Source: Wikipedia award pages."><T t={aw.table} filename="player_awards" searchable={false} /></Block>}
          </>}
        </>}
        {tab === "Top lists" && <>
          <div className="mb-4"><Segmented label="Rank by" value={metric} onChange={setMetric} options={["goals", "assists", "appearances", "minutes_played"]} /></div>
          {metric === "assists" && <p className="mb-2 text-xs" style={{ color: "var(--c-muted)" }}>Assists are a partial measure (see warning above).</p>}
          <ChartSection key={metric} spec={{ id: "an.top_players", fixed: { measure: metric, n: 25 } }} />
          <T t={top.table} filename={`top_${metric}`} pageSize={25} />
        </>}
        {tab === "Compare players" && <>
          <div className="mb-5 grid gap-6 md:grid-cols-2"><PlayerPick label="Player 1" term={t1} setTerm={setT1} value={k1 || undefined} setValue={setP1} /><PlayerPick label="Player 2" term={t2} setTerm={setT2} value={k2 || undefined} setValue={setP2} /></div>
          {k1 && k2 ? <><ChartSection key={`${k1}-${k2}`} spec={{ id: "an.player_compare", fixed: { p1: Number(k1), p2: Number(k2) } }} /><T t={totals} searchable={false} filename="player_comparison" />
            <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Different positions, eras and competitions: totals are not a verdict on who is better.</p></> : <Callout tone="info">Search for two players.</Callout>}
        </>}
      </div>
    </div>
  );
}
const PageHeader2 = () => <header className="mb-5"><h1 className="font-display text-2xl font-bold sm:text-3xl">Player analytics</h1></header>;
