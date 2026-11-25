"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartSpec } from "@/lib/chat";

export function ChartPanel({ chart }: { chart: ChartSpec }) {
  const data = chart.series[0]?.points.map((p) => ({
    x: p.x,
    y: p.y,
  })) ?? [];

  return (
    <figure className="rounded-[14px] border border-[var(--m-hair)] bg-[var(--m-glass2)] p-4">
      <figcaption className="mb-3 text-sm font-semibold text-[var(--m-text)]">
        {chart.title}
      </figcaption>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === "bar" ? (
            <BarChart data={data}>
              <CartesianGrid stroke="var(--m-hair)" vertical={false} />
              <XAxis dataKey="x" tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <YAxis tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="y" fill="var(--m-accent)" radius={4} />
            </BarChart>
          ) : chart.type === "scatter" ? (
            <ScatterChart>
              <CartesianGrid stroke="var(--m-hair)" />
              <XAxis dataKey="x" tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <YAxis dataKey="y" tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <Tooltip />
              <Scatter data={data} fill="var(--m-accent)" />
            </ScatterChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid stroke="var(--m-hair)" vertical={false} />
              <XAxis dataKey="x" tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <YAxis tick={{ fill: "var(--m-faint)", fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="y"
                stroke="var(--m-accent)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="mt-2 font-mono text-[11px] text-[var(--m-faint)]">
        {chart.type} · {data.length} points · {chart.y.label}
      </div>
    </figure>
  );
}
