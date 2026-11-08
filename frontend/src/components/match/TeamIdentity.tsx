import CountryFlag from "../CountryFlag";
import { abbr, isPlaceholder } from "../../data/countries";

/** Flag + name (+ 3-letter abbreviation). Long names wrap instead of overflowing. */
export default function TeamIdentity({ name, size = "md", align = "left", showAbbr = false }: { name: string; size?: "sm" | "md" | "lg" | "xl"; align?: "left" | "right" | "center"; showAbbr?: boolean }) {
  const px = { sm: 20, md: 28, lg: 44, xl: 88 }[size]; const txt = { sm: "text-sm", md: "text-sm sm:text-base", lg: "text-lg", xl: "text-[12px] tracking-normal sm:text-2xl sm:tracking-wide" }[size];
  return (
    <div className={`flex min-w-0 items-center gap-3 ${align === "center" ? "flex-col text-center" : align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <CountryFlag country={name} size={px} className={size === "xl" ? "!rounded-md shadow-xl max-w-[22vw]" : ""} />
      <div className="min-w-0">
        <div className={`${txt} font-display font-bold uppercase leading-tight tracking-wide`} style={{ overflowWrap: "break-word", hyphens: "none" }}>{name}</div>
        {showAbbr && !isPlaceholder(name) && <div className="text-xs font-semibold tracking-[0.2em] opacity-60">{abbr(name)}</div>}
      </div>
    </div>
  );
}
