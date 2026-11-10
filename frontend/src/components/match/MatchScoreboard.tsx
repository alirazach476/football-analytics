import { motion } from "framer-motion";
import { CalendarDays, Flag as RefIcon, MapPin, Users } from "lucide-react";
import { Theme } from "../../theme/editions";
import { teamPalette } from "../../data/teamColors";
import { abbr, isPlaceholder } from "../../data/countries";
import CountryFlag from "../CountryFlag";
import { MatchRow, compLabel, dateLabel, editionLabel, fmtMinute, stageLine, statusOf } from "./matchUtils";
import MatchStatusBadge from "./MatchStatusBadge";
import PlayerLink from "../PlayerLink";

export interface TimelineEvt { minute?: number | null; minute_added?: number | null; kind: string; detail_type?: string | null; card?: string | null; team_name: string; player?: string | null; other_player?: string | null; assist?: string | null; player_key?: number | null; assist_key?: number | null; side: "home" | "away"; scoring_side: "home" | "away" }

/** Lower-third scorer tags: angled team-colour tags with a white minute box, sliding in one after the other. */
export function GoalScorers({ events, side, color }: { events: TimelineEvt[]; side: "home" | "away"; color: string }) {
  const goals = events.filter((e) => (e.kind === "Goal" || e.kind === "Own goal") && e.scoring_side === side);
  return (
    <ul className={`space-y-1.5 ${side === "home" ? "items-end" : "items-start"} flex flex-col`} aria-label={`${side} goal scorers`}>
      {goals.map((g, i) => (
        <motion.li key={i} initial={{ opacity: 0, x: side === "home" ? -30 : 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 + i * 0.12 }}
          className={`flex max-w-full items-stretch overflow-hidden text-sm shadow-lg ${side === "home" ? "flex-row-reverse bc-slant-l" : "bc-slant-r"}`} style={{ background: `linear-gradient(${side === "home" ? 270 : 90}deg, ${color}, color-mix(in srgb, ${color} 55%, #000))` }}>
          <span className="grid min-w-[3.3rem] place-items-center bg-white px-2 font-display text-base font-bold tabular-nums text-slate-900">{fmtMinute(g.minute, g.minute_added)}</span>
          <span className="truncate px-3 py-1 font-semibold text-white"><PlayerLink id={g.player_key} name={g.player ?? "Goal"} />{g.kind === "Own goal" && <b className="ml-1.5 text-[10px] uppercase text-red-200">own goal</b>}{g.detail_type === "Penalty" && g.kind === "Goal" && <b className="ml-1.5 text-[10px] uppercase text-white/80">pen</b>}{g.assist && <span className="ml-2 text-[11px] font-medium text-white/80">assist <PlayerLink id={g.assist_key} name={g.assist} /></span>}</span>
        </motion.li>))}
    </ul>
  );
}

function Side({ name, side, color, color2, winner, played }: { name: string; side: "home" | "away"; color: string; color2: string; winner: boolean; played: boolean }) {
  return (
    <motion.div initial={{ opacity: 0, x: side === "home" ? -60 : 60 }} animate={{ opacity: 1, x: 0 }} transition={{ type: "spring", damping: 22, stiffness: 120 }} className="relative flex min-w-0 flex-col items-center text-center">
      {winner && <span className="mb-1 rounded-sm bg-yellow-300 px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-[0.2em] text-slate-900">Winner</span>}
      <div className="relative" style={{ transform: `rotate(${side === "home" ? -3 : 3}deg)` }}>
        <div className="absolute -inset-3 rounded-2xl opacity-70 blur-xl" style={{ background: color }} />
        <div className="relative rounded-xl border-[3px] border-white bg-white p-0.5 shadow-2xl"><CountryFlag country={name} size={110} className="!rounded-lg !shadow-none max-w-[24vw]" /></div>
      </div>
      <div className="mt-4 w-full font-display font-bold uppercase leading-none tracking-wide" style={{ fontSize: "clamp(.95rem, 3.2vw, 2.1rem)", overflowWrap: "break-word", textShadow: "0 3px 14px rgba(0,0,0,.6)" }}>{name}</div>
      <div className="mt-2 flex h-1.5 w-3/4 max-w-[220px] overflow-hidden" style={{ transform: "skewX(-20deg)" }}><span className="flex-[3]" style={{ background: color }} /><span className="flex-1" style={{ background: color2 }} /></div>
      {!isPlaceholder(name) && <div className="mt-1.5 text-xs font-bold tracking-[0.3em] opacity-70">{abbr(name)}</div>}
      {played && !winner && <span className="sr-only">not the winner</span>}
    </motion.div>
  );
}

/** Broadcast-style scoreboard: stadium-lights stage with the edition artwork, team-coloured diagonal panels with ghost lettering, flag frames, a sculpted score capsule, status ribbon, scorer lower-third and a stats ticker. */
export default function MatchScoreboard({ match: m, events = [], theme, goalsComplete }: { match: MatchRow; events?: TimelineEvt[]; theme: Theme; goalsComplete?: boolean }) {
  const { status, detail } = statusOf(m); const played = m.is_played && m.home_score != null;
  const [hc, hc2] = teamPalette(m.home_team_name, [theme.primary, theme.secondary]); const [ac, ac2] = teamPalette(m.away_team_name, [theme.secondary, theme.accent]);
  const hw = !!played && (m.home_score! > m.away_score! || !!(m.had_shootout && m.shootout_winner_side === "home")); const aw = !!played && (m.away_score! > m.home_score! || !!(m.had_shootout && m.shootout_winner_side === "away"));
  const facts = [
    { icon: <CalendarDays size={14} />, text: dateLabel(m.match_date, { weekday: "long", day: "numeric", month: "long", year: "numeric" }) },
    { icon: <MapPin size={14} />, text: [m.venue_name ?? "Venue to be confirmed", m.venue_city].filter(Boolean).join(", ") },
    m.referee_name ? { icon: <RefIcon size={14} />, text: `Referee: ${m.referee_name}` } : null,
    m.attendance ? { icon: <Users size={14} />, text: `Attendance ${Number(m.attendance).toLocaleString()}` } : null,
  ].filter(Boolean) as { icon: JSX.Element; text: string }[];
  const hasGoals = events.some((e) => e.kind === "Goal" || e.kind === "Own goal");
  const digit = (v: React.ReactNode, win: boolean, k: string) => <motion.span key={k} initial={{ y: -40, opacity: 0, rotateX: 80 }} animate={{ y: 0, opacity: 1, rotateX: 0 }} transition={{ delay: 0.3, type: "spring", damping: 14 }} className="inline-block" style={{ opacity: win || !played ? 1 : 0.8 }}>{v}</motion.span>;
  return (
    <section className="relative isolate overflow-hidden text-white shadow-2xl" style={{ background: "#050a14", borderRadius: "var(--r)", boxShadow: `0 40px 90px -40px ${theme.primary}, 0 0 0 1px rgba(255,255,255,.12)` }} aria-label="Match scoreboard">
      {/* stage */}
      {theme.banner && <img src={theme.banner} alt="" className="absolute inset-0 -z-30 h-full w-full object-cover opacity-45 saturate-125" />}
      <div className="absolute inset-0 -z-20" style={{ background: `radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, ${theme.primary} 38%, transparent), transparent 62%), linear-gradient(180deg, rgba(5,10,20,.55), rgba(5,10,20,.94))` }} />
      <div className="bc-slant-l absolute inset-y-0 left-0 -z-10 w-[58%] pulse-glow" style={{ background: `linear-gradient(90deg, ${hc}cc, ${hc}22 70%, transparent)` }} />
      <div className="bc-slant-r absolute inset-y-0 right-0 -z-10 w-[58%] pulse-glow" style={{ background: `linear-gradient(270deg, ${ac}cc, ${ac}22 70%, transparent)` }} />
      <div className="absolute inset-0 -z-10 opacity-50" style={{ backgroundImage: "linear-gradient(90deg, transparent 49.8%, rgba(255,255,255,.12) 50%, transparent 50.2%), radial-gradient(circle at 50% 52%, transparent 78px, rgba(255,255,255,.12) 79px 81px, transparent 82px)" }} />
      <div className="ghost-text absolute -bottom-6 left-2 -z-10 hidden text-[17vw] sm:block" style={{ WebkitTextStroke: `2px ${hc}66` }} aria-hidden>{isPlaceholder(m.home_team_name) ? "" : abbr(m.home_team_name)}</div>
      <div className="ghost-text absolute -bottom-6 right-2 -z-10 hidden text-[17vw] sm:block" style={{ WebkitTextStroke: `2px ${ac}66` }} aria-hidden>{isPlaceholder(m.away_team_name) ? "" : abbr(m.away_team_name)}</div>

      {/* ribbon */}
      <header className="flex flex-wrap items-stretch justify-between gap-y-2">
        <div className="bc-slant-l flex items-center gap-3 py-2 pl-4 pr-12 sm:pr-16" style={{ background: `linear-gradient(90deg, ${theme.primary}, color-mix(in srgb, ${theme.primary} 60%, ${theme.secondary}))`, color: "var(--c-on-primary)" }}>
          <img src={theme.logo} alt={`${compLabel(m)} ${editionLabel(m.season_id)} logo`} className="h-11 w-11 rounded-lg bg-white p-1 object-contain shadow-lg" />
          <div className="leading-tight"><div className="font-display text-base font-bold uppercase tracking-[0.12em] sm:text-lg">{compLabel(m)} {editionLabel(m.season_id)}</div><div className="text-[11px] font-bold uppercase tracking-[0.2em] opacity-85">{stageLine(m)}</div></div>
        </div>
        <div className="flex items-center gap-3 px-4 py-2"><MatchStatusBadge status={status} />{m.matchday ? <span className="hidden text-xs font-bold uppercase tracking-widest opacity-75 sm:inline">Matchday {m.matchday}</span> : null}</div>
      </header>

      {/* teams + score */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-3 pb-8 pt-6 sm:gap-6 sm:px-10 sm:pb-12 sm:pt-8">
        <Side name={m.home_team_name} side="home" color={hc} color2={hc2} winner={hw} played={!!played} />
        <div className="relative px-1 text-center sm:px-4">
          <div className="bc-slant bc-sheen relative px-4 py-3 shadow-2xl sm:px-10 sm:py-5" style={{ background: `linear-gradient(135deg, ${theme.primary}, color-mix(in srgb, ${theme.primary} 45%, #000))`, color: "var(--c-on-primary)" }}>
            <div className="bc-score flex items-center justify-center gap-2 sm:gap-4" style={{ fontSize: "clamp(2.6rem, 9vw, 6.5rem)", perspective: 400 }}>
              {digit(played ? m.home_score : "–", hw, "h")}<span className="opacity-50" style={{ fontSize: ".6em" }}>:</span>{digit(played ? m.away_score : "–", aw, "a")}
            </div>
          </div>
          {played && m.had_shootout && m.home_pen != null && <div className="mx-auto mt-2 inline-block bg-yellow-300 px-3 py-0.5 font-display text-sm font-bold uppercase tracking-widest text-slate-900" style={{ clipPath: "polygon(6% 0,100% 0,94% 100%,0 100%)" }}>Penalties {m.home_pen}–{m.away_pen}</div>}
          {detail && !m.had_shootout && <div className="mt-2 text-xs font-bold uppercase tracking-[0.25em] opacity-85">{detail}</div>}
          {played && m.home_score_ht != null && <div className="mt-1 text-xs font-semibold tracking-widest opacity-65">HT {m.home_score_ht}–{m.away_score_ht}</div>}
          {!played && <div className="mx-auto mt-3 max-w-[16rem] text-xs font-semibold opacity-85">{m.fixture_detail ?? "Kick-off time to be confirmed"}</div>}
        </div>
        <Side name={m.away_team_name} side="away" color={ac} color2={ac2} winner={aw} played={!!played} />
      </div>

      {/* scorers lower-third */}
      {hasGoals && (
        <div className="grid grid-cols-2 gap-4 px-4 pb-5 sm:px-10">
          <GoalScorers events={events} side="home" color={hc} /><GoalScorers events={events} side="away" color={ac} />
          {goalsComplete === false && <p className="col-span-2 text-center text-[11px] opacity-60">Recorded goal events do not add up to the final score for this match, so the scorers list may be incomplete.</p>}
        </div>)}

      {/* ticker */}
      <footer className="flex flex-wrap gap-x-6 gap-y-1.5 border-t-2 px-4 py-2.5 text-xs sm:px-10" style={{ borderColor: theme.primary, background: "rgba(0,0,0,.55)" }}>
        {facts.map((f, i) => <span key={i} className="inline-flex items-center gap-1.5 font-medium"><span style={{ color: theme.accent }}>{f.icon}</span>{f.text}</span>)}
      </footer>
    </section>
  );
}
