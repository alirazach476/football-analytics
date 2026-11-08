import { Suspense, lazy, useRef, useState } from "react";
import { AlertCircle, BarChart3, Code2, Download, FileImage, Image as ImageIcon, Table2 } from "lucide-react";
import { ChartPayload, Filters, downloadExport, saveBlob } from "../api";
import DataTable, { toCsv } from "./DataTable";
import { Skeleton } from "./ui";

const Plot = lazy(() => import("./Plot"));

export interface PickedPoint { x: any; y: any; customdata: any; pointIndex: number; curveNumber: number }
export interface ExportInfo { id: string; filters: Filters; params: Record<string, any> }

export const footnote = (p: ChartPayload) => [p.n ? `n = ${p.n.toLocaleString("en-US")} ${p.unit}` : "", p.source ? `source: ${p.source}` : "", p.note].filter(Boolean).join(" · ");
const plain = (t: any): string => String(typeof t === "string" ? t : t?.text ?? "").replace(/<[^>]+>/g, "");

const Btn = ({ onClick, children, ...r }: { onClick: () => void; children: React.ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) =>
  <button className="cbtn inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold transition" onClick={onClick} {...r}>{children}</button>;

export default function ChartCard({ payload, loading, error, title, onSelect, exportInfo, height }: { payload?: ChartPayload; loading?: boolean; error?: unknown; title?: string; onSelect?: (pts: PickedPoint[]) => void; exportInfo?: ExportInfo; height?: number }) {
  const [table, setTable] = useState(false); const [msg, setMsg] = useState<string | null>(null); const gd = useRef<any>(null);
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(null), 4000); };
  if (error) return <div className="card flex items-start gap-3 p-5 text-sm"><AlertCircle className="mt-0.5 shrink-0 text-red-400" size={18} /><div><b>Could not load this chart.</b><div className="mt-1" style={{ color: "var(--c-muted)" }}>{String((error as Error).message ?? error)}</div></div></div>;
  if (!payload) return <div className="card p-4"><Skeleton h={height ?? 320} /></div>;
  if (!payload.available) return (
    <div className="card flex items-start gap-3 p-5 text-sm" role="status"><AlertCircle className="mt-0.5 shrink-0" size={18} style={{ color: "var(--c-muted)" }} />
      <div><b>Not shown.</b> <span style={{ color: "var(--c-muted)" }}>{payload.reason}</span><div className="mt-1 text-xs" style={{ color: "var(--c-muted)" }}>This chart is drawn only when the underlying fields exist; nothing is estimated.</div></div></div>);
  const fig = payload.figure!;
  const name = payload.name || title || "chart";
  const heading = plain(fig.layout?.title) || title || name.replace(/_/g, " ");
  const margin = { ...(fig.layout?.margin ?? {}) }; margin.t = Math.max(34, (margin.t ?? 60) - 30);
  const pngClient = async () => { const { Plotly } = await import("./Plot"); await Plotly.downloadImage(gd.current, { format: "png", filename: name, scale: 2 }); };
  const exp = async (fmt: "html" | "png") => { if (!exportInfo) return; try { await downloadExport(exportInfo.id, exportInfo.filters, exportInfo.params, fmt, name); } catch (e) { flash((e as Error).message); } };
  return (
    <div className={`chart-card relative transition ${loading ? "opacity-70" : ""}`} style={{ boxShadow: "0 24px 50px -28px var(--c-primary), 0 0 0 1px var(--c-border)" }}>
      <div className="chart-head"><h3 className="relative z-10 flex min-w-0 items-center gap-2 font-display text-base font-bold uppercase tracking-wide sm:text-lg"><BarChart3 size={18} className="shrink-0" /><span className="truncate">{heading}</span></h3>
        {payload.n ? <span className="relative z-10 rounded-full bg-black/25 px-2.5 py-0.5 text-[11px] font-bold tabular-nums">n = {payload.n.toLocaleString("en-US")}</span> : null}</div>
      <Suspense fallback={<Skeleton h={height ?? fig.layout?.height ?? 360} />}>
        <Plot data={fig.data} layout={{ ...fig.layout, title: { text: "" }, margin, autosize: true, width: undefined, height: height ?? fig.layout?.height }} useResizeHandler style={{ width: "100%" }}
          config={{ displaylogo: false, responsive: true, toImageButtonOptions: { format: "png", filename: name, scale: 2 }, modeBarButtonsToRemove: ["lasso2d"] }}
          onInitialized={(_: unknown, g: any) => (gd.current = g)} onUpdate={(_: unknown, g: any) => (gd.current = g)}
          onClick={onSelect ? (e: any) => onSelect(e.points.map((p: any) => ({ x: p.x, y: p.y, customdata: p.customdata, pointIndex: p.pointIndex, curveNumber: p.curveNumber }))) : undefined} />
      </Suspense>
      <div className="chart-foot px-4 py-2.5 text-xs">
        <p>{footnote(payload)}</p>
        <div className="no-print mt-2 flex flex-wrap items-center gap-1.5">
          <Btn onClick={() => setTable((t) => !t)} aria-expanded={table}><Table2 size={13} />Table view</Btn>
          <Btn onClick={() => saveBlob(new Blob([toCsv(payload.data)], { type: "text/csv" }), `${name}.csv`)}><Download size={13} />CSV</Btn>
          <Btn onClick={pngClient}><ImageIcon size={13} />PNG</Btn>
          {exportInfo && <Btn onClick={() => exp("html")}><Code2 size={13} />Interactive HTML</Btn>}
          {exportInfo && payload.hasStatic && <Btn onClick={() => exp("png")}><FileImage size={13} />PNG (Matplotlib / Seaborn)</Btn>}
          {msg && <span className="text-red-400">{msg}</span>}
        </div>
        {table && <div className="mt-3" style={{ color: "var(--c-ink)" }}><DataTable table={payload.data} pageSize={10} filename={name} dense /></div>}
      </div>
    </div>
  );
}
