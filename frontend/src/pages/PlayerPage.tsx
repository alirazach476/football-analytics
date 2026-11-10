import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Cake, Goal, Medal, Shield, Timer, Trophy } from "lucide-react";
import { Table } from "../api";
import { useThemeOverride } from "../theme/useTheme";
import { Callout, KpiCard, Section, Skeleton, Tabs } from "../components/ui";
import CountryFlag from "../components/CountryFlag";
import DataTable from "../components/DataTable";
import ChartSection from "../components/ChartSection";
import { dateLabel } from "../components/match/matchUtils";

interface Detail {
  profile: { player_key: number; full_name: string; nationality: string | null; date_of_birth: string | null; primary_position: string | null; n_source_ids: number; age?: number };
  totals: { appearances: number; goals: number; assists: number; minutes: number; tournaments: number; teams: string[] };
  byEdition: Table; awards: Table; appearances: Table;
}

/** Player page: flag, profile, career totals, goals per tournament, every appearance (each row opens its match) and awards. */
export default function PlayerPage() {
  const { key = "" } = useParams(); const nav = useNavigate(); const [tab, setTab] = useState("Overview");
  const q = useQuery({ queryKey: ["player", key], queryFn: async () => { const r = await fetch(`/api/players/${key}`); if (!r.ok) throw new Error(r.statusText); return (await r.json()) as Detail; }, staleTime: 300_000 });
  const d = q.data; const latest = d?.byEdition.rows.length ? d.byEdition.rows[d.byEdition.rows.length - 1].season_id : null;
  useThemeOverride(latest);                                      // the page takes the theme of the player's most recent tournament
  if (q.isError) return <Navigate to="/analytics/players" replace />;
  if (!d) return <Skeleton h={520} />;
  const p = d.profile; const t = d.totals; const tabs = ["Overview", "Matches", ...(d.awards.rows.length ? ["Awards"] : []), "Profile & notes"];
  const cur = tabs.includes(tab) ? tab : "Overview";
  const country = p.nationality ?? t.teams[0] ?? null;            // no recorded nationality: show the national team they played for, labelled as such
  const flagOf = (c?: string | null) => (c ? <CountryFlag country={c} size={34} /> : null);
  return (
    <div>
      <section className="hero mb-8 text-white" style={{ background: "linear-gradient(120deg, var(--c-hero-from), var(--c-hero-to))", minHeight: 260, boxShadow: "0 40px 90px -45px var(--c-primary)" }}>
        <div className="pattern-rings absolute inset-0 -z-10 opacity-50" />
        <div className="absolute inset-0 -z-10" style={{ background: "linear-gradient(95deg, rgba(4,8,18,.82), rgba(4,8,18,.35))" }} />
        <div className="ghost-text absolute -bottom-3 right-4 -z-10 hidden max-w-[60%] truncate text-[9vw] md:block" aria-hidden>{p.full_name.split(" ").slice(-1)[0]}</div>
        <div className="flex flex-wrap items-center gap-8 p-6 sm:p-10">
          <motion.div initial={{ scale: 0.8, opacity: 0, rotate: -4 }} animate={{ scale: 1, opacity: 1, rotate: 0 }} className="rounded-2xl border-[3px] border-white bg-white p-0.5 shadow-2xl">
            {country ? <CountryFlag country={country} size={150} className="!rounded-xl !shadow-none" title={`${country} flag`} /> : <div className="grid h-[112px] w-[150px] place-items-center text-4xl">⚽</div>}
          </motion.div>
          <div className="min-w-0 flex-1">
            <span className="inline-block px-3 py-1 text-xs font-bold uppercase tracking-[0.24em]" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)", clipPath: "polygon(0 0,100% 0,94% 100%,0 100%)" }}>Player</span>
            <h1 className="display-caps mt-2 text-4xl font-extrabold leading-[1] sm:text-6xl" style={{ overflowWrap: "anywhere" }}>{p.full_name}</h1>
            <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold uppercase tracking-wider">
              {country && <span className="bc-slant flex items-center gap-2 bg-white/15 px-4 py-1.5 backdrop-blur">{flagOf(country)}{p.nationality ? country : `Plays for ${country}`}</span>}
              {p.primary_position && <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><Shield size={12} className="mr-1 inline" />{p.primary_position}</span>}
              {p.date_of_birth && <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><Cake size={12} className="mr-1 inline" />{dateLabel(p.date_of_birth, { day: "numeric", month: "long", year: "numeric" })}{p.age ? ` · ${p.age}` : ""}</span>}
              {t.teams.filter((x) => x !== country).map((x) => <span key={x} className="bc-slant flex items-center gap-2 bg-white/15 px-4 py-1.5 backdrop-blur"><CountryFlag country={x} size={20} />{x}</span>)}
            </div>
          </div>
        </div>
      </section>

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-5">
        <KpiCard label="Appearances" value={t.appearances} icon={<Shield size={16} />} /><KpiCard label="Goals" value={t.goals} icon={<Goal size={16} />} />
        <KpiCard label="Assists (where recorded)" value={t.assists} icon={<Medal size={16} />} /><KpiCard label="Minutes (known)" value={t.minutes.toLocaleString()} icon={<Timer size={16} />} />
        <KpiCard label="Tournaments" value={t.tournaments} icon={<Trophy size={16} />} />
      </div>
      <Tabs tabs={tabs} value={cur} onChange={setTab} id="pl" />
      <div className="pt-6">
        {cur === "Overview" && <>
          <ChartSection key={p.player_key} spec={{ id: "an.player_edition", fixed: { player_key: p.player_key } }} />
          <Section title="By tournament" hint="Teams link to flags; click a tournament row's team for its page."><DataTable table={d.byEdition} searchable={false} filename={`${p.full_name}_by_edition`} pageSize={30} /></Section>
        </>}
        {cur === "Matches" && <Section title="Every recorded appearance" hint="Click a row to open the match. Goals and assists count only events the sources record; cards are patchy."><DataTable table={d.appearances} filename={`${p.full_name}_matches`} pageSize={20} empty="No appearances recorded." /></Section>}
        {cur === "Awards" && <Section title="Individual awards" hint="Source: Wikipedia award pages."><DataTable table={d.awards} searchable={false} filename={`${p.full_name}_awards`} /></Section>}
        {cur === "Profile & notes" && <div className="space-y-4">
          <div className="card divide-y p-0" style={{ borderColor: "var(--c-border)" }}>{[["Full name", p.full_name], ["Nationality", p.nationality ?? "not recorded"], ["Position (where known)", p.primary_position ?? "not recorded"], ["Date of birth", p.date_of_birth ?? "not recorded"], ["Merged from", `${p.n_source_ids} source id(s)`]].map(([k, v]) =>
            <div key={k} className="grid gap-1 p-3 sm:grid-cols-[12rem_1fr]" style={{ borderColor: "var(--c-border)" }}><span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--c-primary)" }}>{k}</span><span className="flex items-center gap-2 text-sm">{k === "Nationality" && p.nationality && <CountryFlag country={p.nationality} size={22} />}{v}</span></div>)}</div>
          <Callout tone="info" title="What these numbers cover">Only the four collected competitions (not club or full international careers). Goals are goals linked to this player; assists exist only in editions whose sources record them; minutes are approximate for Wikipedia-based editions. <button className="underline" onClick={() => nav("/analytics/players")}>Back to player analytics</button> · <Link to="/fixtures" className="underline">Fixtures</Link></Callout>
        </div>}
      </div>
    </div>
  );
}
