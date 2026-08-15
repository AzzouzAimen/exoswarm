"use client";

import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export function ScientificPlotPanel() {
  return (
    <section className="panel min-h-72">
      <p className="eyebrow">Scientific evidence</p>
      <Plot
        data={[]}
        layout={{
          autosize: true,
          height: 220,
          margin: { l: 24, r: 24, t: 24, b: 24 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          annotations: [
            {
              text: "No deterministic measurements available",
              showarrow: false,
              font: { color: "#94a3b8", size: 13 },
            },
          ],
          xaxis: { visible: false },
          yaxis: { visible: false },
        }}
        config={{ displayModeBar: false, responsive: true }}
        className="w-full"
        useResizeHandler
      />
    </section>
  );
}

