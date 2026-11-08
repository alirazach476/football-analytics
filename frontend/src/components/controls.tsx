import { ReactNode, useMemo, useRef, useState, useEffect } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cx } from "./ui";

export type Opt = [string | number, string] | string;
const norm = (o: Opt): [string | number, string] => (Array.isArray(o) ? o : [o, String(o)]);

export function Segmented({ label, value, onChange, options }: { label?: string; value: any; onChange: (v: any) => void; options: Opt[] }) {
  return (
    <div>
      {label && <span className="label">{label}</span>}
      <div className="inline-flex flex-wrap gap-1 rounded-xl border p-1" style={{ borderColor: "var(--c-border)", background: "var(--c-surface)" }} role="radiogroup">
        {options.map((o) => { const [v, l] = norm(o); const on = String(v) === String(value);
          return <button key={String(v)} role="radio" aria-checked={on} onClick={() => onChange(v)} className="rounded-lg px-3 py-1 text-sm font-medium transition"
            style={{ background: on ? "var(--c-primary)" : "transparent", color: on ? "var(--c-on-primary)" : "var(--c-ink)" }}>{l}</button>; })}
      </div>
    </div>
  );
}

export function SelectField({ label, value, onChange, options, placeholder }: { label?: string; value: any; onChange: (v: any) => void; options: Opt[]; placeholder?: string }) {
  return (
    <label className="block min-w-[10rem]">
      {label && <span className="label">{label}</span>}
      <select className="field" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => { const [v, l] = norm(o); return <option key={String(v)} value={String(v)}>{l}</option>; })}
      </select>
    </label>
  );
}

export function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button role="switch" aria-checked={value} onClick={() => onChange(!value)} className="flex items-center gap-2 text-sm font-medium">
      <span className="relative h-5 w-9 rounded-full transition" style={{ background: value ? "var(--c-primary)" : "color-mix(in srgb, var(--c-muted) 40%, transparent)" }}>
        <span className="absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all" style={{ left: value ? 18 : 2 }} />
      </span>
      {label}
    </button>
  );
}

export function Slider({ label, value, onChange, min, max, step = 1 }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number }) {
  return (
    <label className="block min-w-[12rem]">
      <span className="label">{label}: <b style={{ color: "var(--c-ink)" }}>{value}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full" style={{ accentColor: "var(--c-primary)" }} />
    </label>
  );
}

export function MultiSelect({ label, value, onChange, options, placeholder = "All", max, searchable = true }: { label?: string; value: string[]; onChange: (v: string[]) => void; options: Opt[]; placeholder?: string; max?: number; searchable?: boolean }) {
  const [open, setOpen] = useState(false); const [q, setQ] = useState(""); const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const opts = useMemo(() => options.map(norm), [options]);
  const shown = useMemo(() => opts.filter(([, l]) => l.toLowerCase().includes(q.toLowerCase())).slice(0, 300), [opts, q]);
  const labelOf = (v: string) => opts.find(([x]) => String(x) === v)?.[1] ?? v;
  const toggle = (v: string) => { const has = value.includes(v); const next = has ? value.filter((x) => x !== v) : [...value, v]; onChange(max && next.length > max ? next.slice(-max) : next); };
  return (
    <div className="relative min-w-[12rem]" ref={ref}>
      {label && <span className="label">{label}</span>}
      <button type="button" className="field flex min-h-[2.4rem] items-center justify-between gap-2 text-left" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}>
        <span className="flex flex-wrap gap-1">
          {value.length === 0 ? <span style={{ color: "var(--c-muted)" }}>{placeholder}</span> : value.slice(0, 3).map((v) => (
            <span key={v} className="chip">{labelOf(v)}<X size={12} className="cursor-pointer" onClick={(e) => { e.stopPropagation(); toggle(v); }} /></span>))}
          {value.length > 3 && <span className="chip">+{value.length - 3}</span>}
        </span>
        <ChevronDown size={16} style={{ color: "var(--c-muted)" }} />
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-full min-w-[14rem] overflow-hidden rounded-xl border shadow-card" style={{ background: "var(--c-surface-solid)", borderColor: "var(--c-border)" }}>
          {searchable && <div className="flex items-center gap-2 border-b px-3 py-2" style={{ borderColor: "var(--c-border)" }}><Search size={14} style={{ color: "var(--c-muted)" }} />
            <input autoFocus className="w-full bg-transparent text-sm outline-none" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} /></div>}
          <ul role="listbox" className="max-h-64 overflow-auto py-1">
            {shown.map(([v, l]) => { const on = value.includes(String(v));
              return <li key={String(v)} role="option" aria-selected={on} onClick={() => toggle(String(v))} className="flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm hover:bg-white/10">
                <span>{l}</span>{on && <Check size={14} style={{ color: "var(--c-primary)" }} />}</li>; })}
            {!shown.length && <li className="px-3 py-2 text-sm" style={{ color: "var(--c-muted)" }}>No match</li>}
          </ul>
          {value.length > 0 && <button className="w-full border-t px-3 py-2 text-left text-xs font-semibold" style={{ borderColor: "var(--c-border)", color: "var(--c-primary)" }} onClick={() => onChange([])}>Clear selection</button>}
        </div>
      )}
    </div>
  );
}

export function SearchBox({ label, value, onChange, placeholder }: { label?: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="block min-w-[12rem]">
      {label && <span className="label">{label}</span>}
      <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--c-muted)" }} />
        <input className="field pl-8" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></div>
    </label>
  );
}

export const Row = ({ children, className }: { children: ReactNode; className?: string }) => <div className={cx("flex flex-wrap items-end gap-4", className)}>{children}</div>;
