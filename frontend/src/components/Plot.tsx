import type { ComponentType } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

const Plot = (createPlotlyComponent as (p: unknown) => unknown)(Plotly) as ComponentType<any>;
export { Plotly };
export default Plot;
