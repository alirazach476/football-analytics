import { Suspense, lazy } from "react";
import { Skeleton } from "./ui";

const Plot = lazy(() => import("./Plot"));
const INK = "#1f2937"; const GRID = "rgba(15,23,42,.08)";

/** Small Plotly wrapper for the few analytics charts that are built straight from a query table (the main chart library is rendered server-side). */
export default function QuickPlot({ data, layout, caption, height = 360 }: { data: any[]; layout?: any; caption?: string; height?: number }) {
  return (
    <div className="chart-card mb-4">
      <Suspense fallback={<Skeleton h={height} />}>
        <Plot data={data} useResizeHandler style={{ width: "100%", height }} config={{ displaylogo: false, responsive: true }}
          layout={{ autosize: true, height, paper_bgcolor: "#fcfcfb", plot_bgcolor: "#fcfcfb", font: { family: "Inter, system-ui, sans-serif", size: 13, color: INK }, margin: { l: 60, r: 20, t: 56, b: 60 },
            xaxis: { gridcolor: GRID, automargin: true }, yaxis: { gridcolor: GRID, automargin: true }, legend: { orientation: "h", y: 1.12 }, colorway: ["#2a78d6", "#d9822b", "#2a9d8f", "#9b5de5", "#c2410c", "#64748b"], ...layout }} />
      </Suspense>
      {caption && <p className="border-t px-4 py-2.5 text-xs text-slate-600" style={{ borderColor: "rgba(15,23,42,.08)" }}>{caption}</p>}
    </div>
  );
}
