import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { MatchRow, compLabel, dateLabel, editionLabel, stageLine, statusOf } from "./matchUtils";
import MatchStatusBadge from "./MatchStatusBadge";
import TeamIdentity from "./TeamIdentity";
import { themeFor } from "../../theme/editions";
import { teamPalette } from "../../data/teamColors";

/** Compact broadcast graphic for lists: edition ribbon, two team rows with national-colour edges, a score capsule and a venue strip. The whole card opens the Match Center. */
export default function FixtureCard({ m, showComp = true, onSelect, selected = false }: { m: MatchRow; showComp?: boolean; onSelect?: (m: MatchRow) => void; selected?: boolean }) {
  const Wrap: any = onSelect ? "button" : Link; const wrapProps = onSelect ? { type: "button", onClick: () => onSelect(m), "aria-pressed": selected } : { to: `/match/${m.match_key}` };
  const { status } = statusOf(m); const played = m.is_played && m.home_score != null; const t = themeFor(m.season_id);
  const hw = !!played && (m.home_score! > m.away_score! || !!(m.had_shootout && m.shootout_winner_side === "home")); const aw = !!played && (m.away_score! > m.home_score! || !!(m.had_shootout && m.shootout_winner_side === "away"));
  const row = (name: string, score?: number | null, pen?: number | null, win?: boolean) => {
    const [c] = teamPalette(name, [t.primary, t.secondary]);
    return (
      <div className="relative flex items-stretch overflow-hidden" style={{ background: `linear-gradient(90deg, ${c}55, transparent 55%)` }}>
        <span className="w-1.5 shrink-0" style={{ background: c }} />
        <div className="flex min-w-0 flex-1 items-center justify-between gap-3 px-3 py-2"><TeamIdentity name={name} size="md" />
          <span className="bc-slant flex min-w-[3rem] items-center justify-center gap-1 px-3 py-0.5 font-display text-2xl font-bold tabular-nums" style={{ background: win ? `linear-gradient(135deg, ${t.primary}, color-mix(in srgb, ${t.primary} 55%, #000))` : "rgba(255,255,255,.1)", color: win ? "var(--c-on-primary)" : "#fff" }}>
            {played && m.had_shootout && pen != null && <span className="text-[11px] font-bold text-yellow-300">({pen})</span>}<span>{played ? score : "–"}</span></span></div>
      </div>);
  };
  return (
    <motion.div whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300, damping: 20 }}>
      <Wrap {...wrapProps} className="group relative block w-full overflow-hidden text-left text-white" style={{ background: "#050a14", borderRadius: "var(--r)", boxShadow: selected ? `0 0 0 3px ${t.accent}, 0 18px 40px -20px ${t.primary}` : `0 18px 40px -26px ${t.primary}, 0 0 0 1px rgba(255,255,255,.12)` }}
        aria-label={`${m.home_team_name} v ${m.away_team_name}, ${dateLabel(m.match_date)}`}>
        {t.banner && <img src={t.banner} alt="" className="absolute inset-0 h-full w-full object-cover opacity-25 transition group-hover:scale-105 group-hover:opacity-35" loading="lazy" />}
        <div className="absolute inset-0" style={{ background: `linear-gradient(180deg, color-mix(in srgb, ${t.heroFrom} 55%, transparent), rgba(5,10,20,.9))` }} />
        <div className="relative">
          <div className="flex items-center justify-between gap-2 py-1.5 pl-3 pr-2 text-[11px] font-bold uppercase tracking-[0.12em]" style={{ background: `linear-gradient(90deg, ${t.primary}, color-mix(in srgb, ${t.primary} 55%, transparent))`, color: "var(--c-on-primary)" }}>
            <span className="flex min-w-0 items-center gap-2"><img src={t.logo} alt="" className="h-5 w-5 rounded bg-white p-0.5 object-contain" /><span className="truncate">{showComp ? `${compLabel(m)} ${editionLabel(m.season_id)} · ` : ""}{stageLine(m)}</span></span>
            <MatchStatusBadge status={status} compact text={status === "Scheduled" ? "Coming soon" : status === "Full Time" ? "FT" : status === "Extra Time" ? "AET" : status === "Penalties" ? "PEN" : undefined} />
          </div>
          <div className="space-y-px py-1">{row(m.home_team_name, m.home_score, m.home_pen, hw)}{row(m.away_team_name, m.away_score, m.away_pen, aw)}</div>
          <div className="flex flex-wrap justify-between gap-2 border-t px-3 py-1.5 text-[11px] opacity-80" style={{ borderColor: "rgba(255,255,255,.12)" }}>
            <span className="font-semibold">{dateLabel(m.match_date)}</span><span className="truncate">{[m.venue_name, m.venue_city].filter(Boolean).join(", ") || "venue to be confirmed"}</span>
          </div>
        </div>
      </Wrap>
    </motion.div>
  );
}
