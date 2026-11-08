import { ReactNode } from "react";
import { Table, useApiQuery } from "../../api";
import { Callout, Skeleton } from "../../components/ui";
import DataTable from "../../components/DataTable";

export const COMP_OPTS: [string, string][] = [["WC", "FIFA World Cup"], ["EURO", "UEFA European Championship"], ["COPA", "Copa América"], ["UNL", "UEFA Nations League"]];

/** Query returning a table → { table, rows, isLoading }. */
export function useTable(name: string, args: Record<string, any> = {}, enabled = true) {
  const q = useApiQuery<Table>(name, args, enabled);
  return { table: q.data, rows: (q.data?.rows ?? []) as Record<string, any>[], isLoading: q.isLoading, error: q.error, q };
}
export const n0 = (v: any) => (v == null ? "–" : Number(v).toLocaleString("en-US"));
export const sign = (v: any) => (v == null ? "–" : `${Number(v) > 0 ? "+" : ""}${v}`);

export const ComingSoonNote = ({ n }: { n: number }) => n > 0 ? <Callout tone="soon" title="Coming soon" className="mb-5">{n} fixtures are scheduled and not played yet. They are listed with whatever is known (date, stage, venue) and have no results.</Callout> : null;
export const PredictionBanner = () => <Callout tone="warn" title="Predictions" className="mb-5">Everything labelled <b>prediction</b> below is model output made without knowing the result. It is not an actual result and not betting advice.</Callout>;
export const Loading = ({ h = 160 }: { h?: number }) => <Skeleton h={h} />;

export function Block({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) {
  return <section className="mb-8"><h2 className="font-display text-lg font-bold">{title}</h2>{hint && <p className="mb-2 text-xs" style={{ color: "var(--c-muted)" }}>{hint}</p>}<div className="mt-3">{children}</div></section>;
}
export const T = ({ t, ...p }: { t?: Table; pageSize?: number; filename?: string; hide?: string[]; searchable?: boolean; empty?: string; dense?: boolean; onRowClick?: (r: any) => void }) => <DataTable table={t} {...p} />;
export const pick = (t: Table | undefined, cols: string[]): Table | undefined => t && ({ ...t, columns: cols.filter((c) => t.columns.includes(c)) });
