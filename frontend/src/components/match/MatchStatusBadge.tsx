import { Status } from "./matchUtils";

const STYLE: Record<Status, { bg: string; fg: string }> = {
  Scheduled: { bg: "rgba(250,204,21,.18)", fg: "#facc15" }, Live: { bg: "rgba(239,68,68,.22)", fg: "#fecaca" }, "Half Time": { bg: "rgba(255,255,255,.14)", fg: "#fff" },
  "Full Time": { bg: "rgba(255,255,255,.14)", fg: "#fff" }, "Extra Time": { bg: "rgba(255,255,255,.14)", fg: "#fff" }, Penalties: { bg: "rgba(255,255,255,.14)", fg: "#fff" },
  Postponed: { bg: "rgba(251,146,60,.2)", fg: "#fdba74" }, Abandoned: { bg: "rgba(239,68,68,.18)", fg: "#fca5a5" }, Cancelled: { bg: "rgba(239,68,68,.18)", fg: "#fca5a5" },
};
/** The animated dot is drawn only for status Live, which only occurs when the data itself says the match is live. */
export default function MatchStatusBadge({ status, text, compact = false }: { status: Status; text?: string; compact?: boolean }) {
  const s = STYLE[status]; const label = text ?? (status === "Scheduled" ? "Coming soon" : status === "Full Time" ? "Full time" : status);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md font-bold uppercase tracking-widest ${compact ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs"}`} style={{ background: s.bg, color: s.fg }}>
      {status === "Live" && <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" /><span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" /></span>}
      {label}
    </span>
  );
}
