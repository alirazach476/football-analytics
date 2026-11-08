import { ReactNode, useEffect, useState } from "react";
import { animate, motion } from "framer-motion";
import clsx from "clsx";
import { AlertTriangle, Clock, Info, Sparkles } from "lucide-react";

export const cx = clsx;

export function Callout({ tone = "info", title, children, className }: { tone?: "info" | "warn" | "soon" | "prediction"; title?: string; children: ReactNode; className?: string }) {
  const map = {
    info: { icon: <Info size={18} />, bg: "color-mix(in srgb, var(--c-primary) 12%, transparent)", bd: "var(--c-primary)" },
    warn: { icon: <AlertTriangle size={18} />, bg: "rgba(245,158,11,.14)", bd: "#f59e0b" },
    soon: { icon: <Clock size={18} />, bg: "rgba(253,224,71,.16)", bd: "#eab308" },
    prediction: { icon: <Sparkles size={18} />, bg: "rgba(167,139,250,.16)", bd: "#a78bfa" },
  }[tone];
  return (
    <div className={cx("flex gap-3 border-l-4 px-4 py-3 text-sm", className)} style={{ background: map.bg, borderColor: map.bd, color: "var(--c-ink)", borderRadius: "calc(var(--r) / 1.6)" }} role="note">
      <span className="mt-0.5 shrink-0" style={{ color: map.bd }}>{map.icon}</span>
      <div>{title && <div className="mb-0.5 font-semibold">{title}</div>}<div style={{ color: "var(--c-ink)", opacity: 0.9 }}>{children}</div></div>
    </div>
  );
}

/** Counts a number up when it first appears (plain text for non-numeric values). */
function CountUp({ value }: { value: ReactNode }) {
  const raw = typeof value === "number" ? value : typeof value === "string" && /^[\d,]+(\.\d+)?$/.test(value) ? Number(value.replace(/,/g, "")) : null;
  const dec = typeof value === "string" && value.includes(".") ? value.split(".")[1].length : 0;
  const [n, setN] = useState(0);
  useEffect(() => { if (raw === null) return; if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setN(raw); return; } const c = animate(0, raw, { duration: 0.9, ease: "easeOut", onUpdate: (v) => setN(v) }); return () => c.stop(); }, [raw]);
  if (raw === null) return <>{value}</>;
  const shown = dec ? n.toFixed(dec) : Math.round(n).toLocaleString("en-US");
  return <>{shown}</>;
}

export function KpiCard({ label, value, hint, icon, accent }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode; accent?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="stat-tile p-4" title={hint}>
      <div className="absolute inset-y-0 left-0 w-1.5" style={{ background: `linear-gradient(180deg, ${accent ?? "var(--c-primary)"}, var(--c-secondary))` }} />
      <div className="flex items-center justify-between pl-1">
        <span className="text-[11px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--c-muted)" }}>{label}</span>
        {icon && <span style={{ color: accent ?? "var(--c-primary)" }}>{icon}</span>}
      </div>
      <div className="relative z-10 mt-1 pl-1 font-display text-4xl font-bold tabular-nums leading-tight sm:text-5xl"><CountUp value={value} /></div>
      {hint && <div className="relative z-10 mt-1 pl-1 text-xs" style={{ color: "var(--c-muted)" }}>{hint}</div>}
    </motion.div>
  );
}

export function Tabs({ tabs, value, onChange, id = "tabs" }: { tabs: string[]; value: string; onChange: (v: string) => void; id?: string }) {
  return (
    <div role="tablist" className="no-scrollbar flex gap-1 overflow-x-auto border-b-2 pb-1.5" style={{ borderColor: "color-mix(in srgb, var(--c-primary) 35%, transparent)" }}>
      {tabs.map((t) => (
        <button key={t} role="tab" aria-selected={t === value} onClick={() => onChange(t)} className="tab-btn" style={{ color: t === value ? undefined : "var(--c-muted)" }}>
          {t === value && <motion.span layoutId={`${id}-bg`} className="tab-bg" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
          {t}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, right, eyebrow }: { title: string; subtitle?: ReactNode; right?: ReactNode; eyebrow?: string }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && <div className="mb-1 inline-block px-3 py-0.5 text-[11px] font-bold uppercase tracking-[0.22em]" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)", clipPath: "polygon(0 0, 100% 0, 94% 100%, 0 100%)" }}>{eyebrow}</div>}
        <h1 className="display-caps text-3xl font-bold leading-tight sm:text-5xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-3xl text-sm" style={{ color: "var(--c-muted)" }}>{subtitle}</p>}
      </div>
      {right}
    </header>
  );
}

export const Skeleton = ({ h = 280, className }: { h?: number; className?: string }) => <div className={cx("skeleton w-full", className)} style={{ height: h }} />;

export function Section({ title, hint, children, right }: { title?: string; hint?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="mb-10">
      {(title || right) && (
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>{title && <h2 className="section-title">{title}</h2>}{hint && <p className="mt-1 text-xs" style={{ color: "var(--c-muted)" }}>{hint}</p>}</div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export const StatusBadge = ({ text }: { text: string }) => {
  const soon = /coming soon/i.test(text);
  return <span className={cx("chip", soon && "chip-soon")}>{text}</span>;
};
