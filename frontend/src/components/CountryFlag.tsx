import "flag-icons/css/flag-icons.min.css";
import { abbr, flagCode, isPlaceholder } from "../data/countries";

/** National flag (SVG, 4:3) for a team name. Unknown / defunct / undecided teams get a neutral badge instead of a flag, so a wrong flag is never shown. */
export default function CountryFlag({ country, size = 24, className = "", title }: { country?: string | null; size?: number; className?: string; title?: string }) {
  const code = flagCode(country); const h = Math.round((size * 3) / 4);
  const label = title ?? (country ? `${country} flag` : "Team to be decided");
  if (code) return <span role="img" aria-label={label} title={country ?? ""} className={`fi fi-${code} inline-block shrink-0 rounded-[3px] shadow-[0_0_0_1px_rgba(255,255,255,.18)] ${className}`} style={{ width: size, height: h, backgroundSize: "cover" }} />;
  const tbd = isPlaceholder(country) || !country;
  return <span role="img" aria-label={label} title={country ?? "To be decided"} className={`inline-grid shrink-0 place-items-center rounded-[3px] text-[9px] font-bold ${className}`}
    style={{ width: size, height: h, background: "color-mix(in srgb, var(--c-muted) 25%, transparent)", color: "var(--c-ink)", border: tbd ? "1px dashed var(--c-muted)" : "1px solid var(--c-border)" }}>{tbd ? "?" : abbr(country).slice(0, 3)}</span>;
}
