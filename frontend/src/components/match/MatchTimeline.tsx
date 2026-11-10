import { ArrowLeftRight, Goal, Square } from "lucide-react";
import CountryFlag from "../CountryFlag";
import { MatchRow, fmtMinute } from "./matchUtils";
import { TimelineEvt } from "./MatchScoreboard";
import PlayerLink from "../PlayerLink";

const icon = (e: TimelineEvt) => {
  if (e.kind === "Goal") return { el: <Goal size={16} />, label: e.detail_type === "Penalty" ? "Penalty goal" : "Goal", color: "#22c55e" };
  if (e.kind === "Own goal") return { el: <Goal size={16} />, label: "Own goal", color: "#f87171" };
  if (/red/i.test(e.kind) || /red/i.test(e.card ?? "")) return { el: <Square size={14} fill="#ef4444" color="#ef4444" />, label: "Red card", color: "#ef4444" };
  if (/yellow/i.test(e.kind) || /yellow/i.test(e.card ?? "")) return { el: <Square size={14} fill="#facc15" color="#facc15" />, label: "Yellow card", color: "#facc15" };
  if (e.kind === "Substitution") return { el: <ArrowLeftRight size={15} />, label: "Substitution", color: "#38bdf8" };
  return { el: <Square size={12} />, label: e.kind, color: "var(--c-muted)" };
};

const sub = (e: TimelineEvt) => (e.kind === "Substitution" ? (e.other_player ? `⇄ ${e.other_player}` : "") : e.kind === "Goal" && e.assist ? `assist ${e.assist}` : "");

function Marker({ text }: { text: string }) {
  return <li className="relative my-3 flex items-center justify-center"><span className="rounded-full border px-4 py-1 text-xs font-bold uppercase tracking-[0.16em]" style={{ borderColor: "var(--c-border)", background: "var(--c-surface-solid)" }}>{text}</span></li>;
}

/** Chronological match timeline (home events left, away events right). Added time is shown as 45+2'. Half-time and full-time markers use the recorded scores. */
export default function MatchTimeline({ events, match: m }: { events: TimelineEvt[]; match: MatchRow }) {
  if (!events.length) return null;
  const items: JSX.Element[] = []; let ht = false, et = false;
  events.forEach((e, i) => {
    const min = e.minute ?? 0;
    if (!ht && min > 45 && m.home_score_ht != null) { ht = true; items.push(<Marker key="ht" text={`Half-time ${m.home_score_ht}–${m.away_score_ht}`} />); }
    if (!et && min > 90 && m.went_beyond_90) { et = true; items.push(<Marker key="et" text="Extra time" />); }
    const ic = icon(e); const home = e.side === "home";
    items.push(
      <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 py-1.5">
        <div className={`flex items-center justify-end gap-2 text-right ${home ? "" : "invisible"}`}>
          <div className="min-w-0"><div className="break-words font-semibold leading-tight"><PlayerLink id={e.player_key} name={e.player ?? ic.label} /></div>{sub(e) && <div className="text-xs" style={{ color: "var(--c-muted)" }}>{sub(e)}</div>}</div>
          <span aria-label={ic.label} title={ic.label} style={{ color: ic.color }}>{ic.el}</span>
        </div>
        <div className="flex w-20 flex-col items-center"><span className="rounded-md px-2 py-0.5 text-sm font-black tabular-nums" style={{ background: "color-mix(in srgb, var(--c-primary) 18%, transparent)", color: "var(--c-primary)" }}>{fmtMinute(e.minute, e.minute_added)}</span></div>
        <div className={`flex items-center gap-2 ${home ? "invisible" : ""}`}>
          <span aria-label={ic.label} title={ic.label} style={{ color: ic.color }}>{ic.el}</span>
          <div className="min-w-0"><div className="break-words font-semibold leading-tight"><PlayerLink id={e.player_key} name={e.player ?? ic.label} /></div>{sub(e) && <div className="text-xs" style={{ color: "var(--c-muted)" }}>{sub(e)}</div>}</div>
        </div>
      </li>);
  });
  const goalScore = m.is_played && m.home_score != null;
  items.push(<Marker key="ft" text={`${m.went_beyond_90 ? "After extra time" : "Full-time"} ${goalScore ? `${m.home_score}–${m.away_score}` : ""}`} />);
  if (m.had_shootout && m.home_pen != null) items.push(<Marker key="pen" text={`Penalty shoot-out ${m.home_pen}–${m.away_pen}`} />);
  return (
    <div className="card p-4 sm:p-6">
      <div className="mb-3 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center text-xs font-bold uppercase tracking-widest" style={{ color: "var(--c-muted)" }}>
        <span className="flex items-center justify-end gap-2"><CountryFlag country={m.home_team_name} size={20} />{m.home_team_name}</span><span className="w-20" /><span className="flex items-center gap-2"><CountryFlag country={m.away_team_name} size={20} />{m.away_team_name}</span>
      </div>
      <ol className="relative">{items}</ol>
    </div>
  );
}
