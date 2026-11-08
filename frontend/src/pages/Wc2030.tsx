import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Building2, CalendarClock, ExternalLink, Flag, Globe2, HelpCircle, ListChecks, MapPin, Sparkles, Trophy, Users } from "lucide-react";
import { useWc2030 } from "../api";
import { THEMES } from "../theme/editions";
import { Callout, KpiCard, Section, Skeleton } from "../components/ui";
import DataTable from "../components/DataTable";

const Status = ({ s }: { s?: string }) => s ? <span className="chip chip-soon ml-2 !text-[10px] uppercase">{s.split(":")[0].split(";")[0].slice(0, 28)}</span> : null;

export default function Wc2030() {
  const { data } = useWc2030(); const t = THEMES["wc-2030"];
  if (!data) return <Skeleton h={500} />;
  const f = data.facts;
  const venues = { columns: ["country", "city", "stadium", "capacity"], rows: f.venues.list, total: f.venues.list.length };
  const cap = f.venues.list.reduce((a: number, v: any) => a + (v.capacity ?? 0), 0);
  return (
    <div>
      <Link to="/competition/wc" className="mb-3 inline-block text-sm font-semibold" style={{ color: "var(--c-primary)" }}>← FIFA World Cup</Link>
      <section className="relative mb-6 overflow-hidden rounded-3xl border" style={{ borderColor: "var(--c-border)", background: `linear-gradient(120deg, ${t.heroFrom}, ${t.heroTo})` }}>
        <img src="/logos/fifa.png" alt="FIFA logo" className="absolute right-4 top-4 h-10 rounded-lg bg-white p-1 object-contain" />
        <div className="pattern-rings absolute inset-0" style={{ filter: "invert(1)", opacity: 0.25 }} />
        <div className="relative flex flex-wrap items-center gap-8 p-6 sm:p-10">
          <motion.img initial={{ scale: 0.8, opacity: 0, rotate: -4 }} animate={{ scale: 1, opacity: 1, rotate: 0 }} src={t.logo} alt="FIFA World Cup 2030 logo" className="h-44 w-44 object-contain drop-shadow-xl sm:h-56 sm:w-56" />
          <div className="min-w-0 flex-1" style={{ color: "#1f1304" }}>
            <span className="chip chip-soon !text-sm"><CalendarClock size={14} />COMING SOON</span>
            <h1 className="mt-3 font-display text-4xl font-extrabold leading-tight sm:text-6xl">{f.title}</h1>
            <p className="mt-1 text-lg font-semibold" style={{ color: t.primary }}>{f.edition} · {f.tagline}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-sm font-semibold">
              {f.hosts.map((h: any) => <span key={h.country} className="rounded-full bg-white/70 px-3 py-1"><Flag size={12} className="mr-1 inline" />{h.country}</span>)}
              <span className="rounded-full bg-white/70 px-3 py-1"><CalendarClock size={12} className="mr-1 inline" />{f.dates.value}</span>
            </div>
          </div>
        </div>
      </section>

      <Callout tone="soon" title="This tournament has not been played" className="mb-6">{f.note}</Callout>

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Host nations" value={f.hosts.length} icon={<Globe2 size={16} />} hint="+3 centenary-match countries" />
        <KpiCard label="Teams" value="48*" icon={<Users size={16} />} hint="*current format; 64 proposed, unconfirmed" accent="#eab308" />
        <KpiCard label="Candidate stadiums" value={f.venues.list.length} icon={<Building2 size={16} />} hint="provisional list" accent="#eab308" />
        <KpiCard label="Matches" value="TBC" icon={<Trophy size={16} />} hint="104 with the 48-team format; not confirmed" accent="#eab308" />
      </div>

      <div className="mb-8 grid gap-4 lg:grid-cols-2">
        <div className="card p-5"><h3 className="mb-2 flex items-center font-display font-bold"><Sparkles size={16} className="mr-2" />Selection<Status s="confirmed" /></h3>
          <p className="text-sm"><b>Decision:</b> {f.selection.decision}.</p><p className="mt-2 text-sm"><b>Bid:</b> {f.selection.bid}.</p></div>
        <div className="card p-5"><h3 className="mb-2 flex items-center font-display font-bold"><CalendarClock size={16} className="mr-2" />Dates<Status s="provisional" /></h3>
          <p className="text-sm"><b>{f.dates.value}.</b></p><p className="mt-2 text-sm" style={{ color: "var(--c-muted)" }}>{f.dates.status}.</p></div>
        <div className="card p-5"><h3 className="mb-2 flex items-center font-display font-bold"><Users size={16} className="mr-2" />Format<Status s="undecided" /></h3>
          <p className="text-sm"><b>Teams:</b> {f.format.teams}.</p><p className="mt-2 text-sm"><b>Matches:</b> {f.format.matches}.</p></div>
        <div className="card p-5"><h3 className="mb-2 flex items-center font-display font-bold"><Sparkles size={16} className="mr-2" />Identity<Status s="partly announced" /></h3>
          <p className="text-sm"><b>{f.identity.name}</b> — {f.identity.meaning}.</p><p className="mt-2 text-sm" style={{ color: "var(--c-muted)" }}>{f.identity.status}.</p>
          <p className="mt-2 text-sm"><b>Mascot:</b> {f.identity.mascot}. <b>Match ball:</b> {f.identity.matchBall}.</p></div>
      </div>

      <Section title="Host countries"><div className="grid gap-4 md:grid-cols-3">
        {f.hosts.map((h: any) => <div key={h.country} className="card p-5"><div className="text-xs font-bold uppercase tracking-widest" style={{ color: "var(--c-primary)" }}>{h.role}</div><div className="font-display text-xl font-bold">{h.country}</div></div>)}</div></Section>

      <Section title="Centenary matches" hint={`${f.centenary.proposedDates} · status: ${f.centenary.status}`}>
        <p className="mb-3 text-sm">{f.centenary.text}</p>
        <div className="grid gap-4 md:grid-cols-3">{f.centenary.matches.map((c: any) => <div key={c.country} className="card p-5"><div className="font-display font-bold">{c.country}</div>
          <div className="mt-1 text-sm"><MapPin size={13} className="mr-1 inline" />{c.city} · {c.stadium}</div><div className="mt-1 text-xs" style={{ color: "var(--c-muted)" }}>{c.note}</div></div>)}</div>
      </Section>

      <Section title="Venues" hint={f.venues.status}>
        <DataTable table={venues} searchable pageSize={25} filename="wc2030_candidate_venues" />
        <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Combined capacity of the listed candidates: {cap.toLocaleString()} seats. Capacities are as reported by the sources; the final list is not confirmed.</p>
      </Section>

      <Section title="Qualification">
        <div className="card divide-y p-0" style={{ borderColor: "var(--c-border)" }}>
          {Object.entries(f.qualification).map(([k, v]) => <div key={k} className="grid gap-1 p-4 sm:grid-cols-[10rem_1fr]" style={{ borderColor: "var(--c-border)" }}>
            <div className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--c-primary)" }}>{k.replace(/([A-Z])/g, " $1")}</div><div className="text-sm">{String(v)}</div></div>)}</div>
      </Section>

      <Section title="Still to be decided" hint="Not confirmed in the sources used: shown as open questions, never filled in with guesses.">
        <ul className="grid gap-2 sm:grid-cols-2">{f.undecided.map((u: string) => <li key={u} className="card flex items-start gap-2 p-3 text-sm"><HelpCircle size={16} className="mt-0.5 shrink-0" style={{ color: "#eab308" }} />{u}</li>)}</ul>
      </Section>

      <Section title="Sources"><ul className="space-y-1.5 text-sm">{data.sources.map((s) => <li key={s.url}><a className="inline-flex items-center gap-1.5 font-medium underline-offset-2 hover:underline" style={{ color: "var(--c-primary)" }} href={s.url} target="_blank" rel="noreferrer"><ListChecks size={14} />{s.label}<ExternalLink size={12} /></a></li>)}</ul></Section>
    </div>
  );
}
