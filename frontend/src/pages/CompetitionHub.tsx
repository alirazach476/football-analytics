import { Link, Navigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useTournaments } from "../api";
import { HUB_THEME, THEMES } from "../theme/editions";
import { Skeleton } from "../components/ui";
import { BODY_OF } from "../components/Brand";
import CountryFlag from "../components/CountryFlag";

const NAMES: Record<string, string> = { WC: "FIFA World Cup", EURO: "UEFA European Championship", COPA: "Copa América", UNL: "UEFA Nations League" };

export default function CompetitionHub() {
  const { comp = "" } = useParams(); const id = comp.toUpperCase(); const { data } = useTournaments();
  if (!NAMES[id]) return <Navigate to="/" replace />;
  const list = (data?.editions ?? []).filter((e) => e.competition === id).slice().reverse();
  const hub = THEMES[HUB_THEME[id]];
  return (
    <div>
      <section className="hero mb-10 text-white" style={{ background: `linear-gradient(120deg, ${hub.heroFrom}, ${hub.heroTo})`, minHeight: 300, boxShadow: `0 40px 90px -45px ${hub.primary}` }}>
        {hub.banner && <img src={hub.banner} alt="" className="absolute inset-0 -z-20 h-full w-full object-cover opacity-80 saturate-125" />}
        <div className={`pattern-${hub.pattern} absolute inset-0 -z-10 opacity-70`} />
        <div className="absolute inset-0 -z-10" style={{ background: "linear-gradient(95deg, rgba(4,8,18,.9), rgba(4,8,18,.5) 55%, rgba(4,8,18,.1))" }} />
        <div className="ghost-text absolute -bottom-6 right-4 -z-10 hidden text-[13vw] md:block" aria-hidden>{id}</div>
        <div className="flex flex-wrap items-center gap-8 p-6 pb-14 sm:p-12 sm:pb-16">
          <img src={hub.logo} alt={`${NAMES[id]} logo`} className="glow-logo h-40 w-40 rounded-3xl bg-white/95 object-contain p-3 sm:h-52 sm:w-52" />
          <div className="min-w-0 flex-1">
            <div className="inline-block px-3 py-1 text-xs font-bold uppercase tracking-[0.24em]" style={{ background: hub.primary, color: "var(--c-on-primary)", clipPath: "polygon(0 0,100% 0,94% 100%,0 100%)" }}>Competition</div>
            <h1 className="display-caps mt-3 text-5xl font-extrabold leading-[.95] sm:text-7xl" style={{ textShadow: "0 6px 40px rgba(0,0,0,.55)" }}>{NAMES[id]}</h1>
            <p className="mt-3 max-w-2xl opacity-90">{id === "UNL" ? "Every Nations League edition shares one logo, so every edition shares one visual identity." : "Choose an edition: each page is built around that edition's own logo, colours and artwork."}</p>
            <div className="mt-4 flex gap-2">{BODY_OF[id].map((b) => <img key={b.id} src={b.logo} alt={`${b.name} logo`} className="h-10 rounded-lg bg-white p-1 object-contain" />)}</div>
          </div>
        </div>
      </section>
      <h2 className="section-title mb-4">Editions</h2>
      {!data ? <Skeleton h={300} /> : <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        {id === "WC" && (() => { const t = THEMES["wc-2030"]; return (
          <motion.div key="wc-2030" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}>
            <Link to="/wc-2030" className="group relative block overflow-hidden transition hover:-translate-y-1" style={{ background: `linear-gradient(135deg, ${t.heroFrom}, ${t.heroTo})`, borderRadius: "var(--r)", minHeight: 230, color: "#1f1304", boxShadow: `0 26px 50px -30px ${t.primary}, 0 0 0 1px rgba(0,0,0,.12)` }}>
              <div className={`pattern-${t.pattern} absolute inset-0 opacity-40`} />
              <div className="ghost-text absolute -right-2 top-1 text-[5.5rem]" style={{ WebkitTextStroke: "2px rgba(0,0,0,.15)" }} aria-hidden>2030</div>
              <div className="relative flex min-h-[230px] flex-col justify-end p-5">
                <img src={t.logo} alt="FIFA World Cup 2030 logo" className="absolute left-5 top-5 h-20 w-20 rounded-2xl bg-white/95 object-contain p-1.5 transition group-hover:-rotate-3 group-hover:scale-110" />
                <div className="font-display text-2xl font-bold uppercase leading-tight">2030 FIFA World Cup</div>
                <div className="mt-0.5 text-xs font-semibold uppercase tracking-wider opacity-80">Morocco · Portugal · Spain</div>
                <div className="mt-3"><span className="chip chip-soon">Coming soon</span></div>
              </div>
            </Link>
          </motion.div>); })()}
        {list.map((e, i) => { const t = THEMES[e.themeKey] ?? hub; const soon = e.status !== "in_data";
          return (
            <motion.div key={e.seasonId} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.05 }}>
              <Link to={`/tournament/${e.slug}`} className="group relative block overflow-hidden text-white transition hover:-translate-y-1" style={{ background: `linear-gradient(135deg, ${t.heroFrom}, ${t.heroTo})`, borderRadius: "var(--r)", minHeight: 230, boxShadow: `0 26px 50px -30px ${t.primary}, 0 0 0 1px rgba(255,255,255,.12)` }}>
                {t.banner && <img src={t.banner} alt="" className="absolute inset-0 h-full w-full object-cover opacity-70 transition duration-700 group-hover:scale-110" />}
                <div className={`pattern-${t.pattern} absolute inset-0 opacity-60`} />
                <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(4,8,18,.1), rgba(4,8,18,.88))" }} />
                <div className="ghost-text absolute -right-2 top-1 text-[5.5rem]" aria-hidden>{e.competition === "UNL" ? e.seasonId.slice(4, 8) : e.year}</div>
                <div className="relative flex h-full min-h-[230px] flex-col justify-end p-5">
                  <img src={t.logo} alt={`${e.edition} logo`} className="glow-logo absolute left-5 top-5 h-20 w-20 rounded-2xl bg-white/95 object-contain p-1.5 transition group-hover:-rotate-3 group-hover:scale-110" />
                  <div className="font-display text-2xl font-bold uppercase leading-tight">{e.edition}</div>
                  <div className="mt-0.5 truncate text-xs font-semibold uppercase tracking-wider opacity-85">{e.host ?? "host to be confirmed"}</div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] font-bold uppercase">
                    {soon ? <span className="chip chip-soon">{e.status === "upcoming" ? "Coming soon" : "Announced"}{e.matchesComingSoon ? ` · ${e.matchesComingSoon} fixtures` : ""}</span>
                      : <><span className="bc-slant px-3 py-1" style={{ background: t.primary, color: "var(--c-on-primary)" }}>{e.matchesPlayed} matches</span>{e.champion && <span className="bc-slant flex items-center gap-1.5 bg-white/20 px-3 py-1 backdrop-blur"><CountryFlag country={e.champion} size={16} />{e.champion}</span>}</>}
                  </div>
                </div>
              </Link>
            </motion.div>); })}
      </div>}
    </div>
  );
}
