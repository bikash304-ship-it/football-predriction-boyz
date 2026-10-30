"use client";

import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";

const NEON = "rgb(var(--neon))";
const SKY = "rgb(var(--sky))";
const MUTED = "rgb(var(--muted))";
const LINE = "rgb(var(--line))";
const tip = {
  contentStyle: { background: "rgb(var(--card))", border: "1px solid rgb(var(--line))", borderRadius: 12, fontSize: 12 },
  labelStyle: { color: "rgb(var(--ink))" },
  itemStyle: { color: "rgb(var(--ink))" },
};

export function GoalsDistChart({ dist, expected }: { dist: number[]; expected: number }) {
  const data = dist.slice(0, 8).map((p, k) => ({ goals: k === 7 ? "7+" : String(k), p: Math.round((k === 7 ? dist.slice(7).reduce((a, b) => a + b, 0) : p) * 1000) / 10 }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="goals" stroke={MUTED} fontSize={11} tickLine={false} label={{ value: "Total goals", position: "insideBottom", offset: -2, fill: MUTED, fontSize: 10 }} />
        <YAxis stroke={MUTED} fontSize={11} tickLine={false} unit="%" />
        <Tooltip {...tip} formatter={(v: number) => [`${v}%`, "Probability"]} />
        <Bar dataKey="p" radius={[6, 6, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={i > expected ? SKY : NEON} fillOpacity={0.85} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TeamCompareChart({ home, away, rows }: { home: string; away: string; rows: { metric: string; home: number | null; away: number | null }[] }) {
  const data = rows.filter((r) => r.home !== null && r.away !== null);
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 38)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }} barGap={2}>
        <CartesianGrid stroke={LINE} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" stroke={MUTED} fontSize={11} tickLine={false} />
        <YAxis type="category" dataKey="metric" stroke={MUTED} fontSize={11} width={112} tickLine={false} />
        <Tooltip {...tip} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="home" name={home} fill={NEON} radius={[0, 4, 4, 0]} />
        <Bar dataKey="away" name={away} fill={SKY} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ProbHistoryChart({ points }: { points: { created_at: string; home: number; draw: number; away: number }[] }) {
  const data = points.map((p) => ({ ...p, t: new Date(p.created_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
        <XAxis dataKey="t" stroke={MUTED} fontSize={10} tickLine={false} />
        <YAxis stroke={MUTED} fontSize={11} unit="%" domain={[0, 100]} tickLine={false} />
        <Tooltip {...tip} />
        <Line type="monotone" dataKey="home" name="Home" stroke={NEON} strokeWidth={2} dot />
        <Line type="monotone" dataKey="draw" name="Draw" stroke={MUTED} strokeWidth={2} dot />
        <Line type="monotone" dataKey="away" name="Away" stroke={SKY} strokeWidth={2} dot />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CalibrationChart({ bins }: { bins: { mean_predicted: number | null; observed_rate: number | null; count: number }[] }) {
  const data = bins.filter((b) => b.count > 0 && b.mean_predicted !== null)
    .map((b) => ({ x: Math.round(b.mean_predicted! * 100), y: Math.round(b.observed_rate! * 100), n: b.count }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 10, right: 16, left: -10, bottom: 10 }}>
        <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" domain={[0, 100]} unit="%" stroke={MUTED} fontSize={11} name="Predicted"
          label={{ value: "Predicted probability", position: "insideBottom", offset: -6, fill: MUTED, fontSize: 10 }} />
        <YAxis type="number" dataKey="y" domain={[0, 100]} unit="%" stroke={MUTED} fontSize={11} name="Observed" />
        <ZAxis type="number" dataKey="n" range={[40, 400]} name="Predictions" />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke={MUTED} strokeDasharray="4 4" />
        <Tooltip {...tip} cursor={{ strokeDasharray: "3 3" }} />
        <Scatter data={data} fill={NEON} fillOpacity={0.8} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function MarketBarChart({ rows }: { rows: { market: string; hit: number; avg: number; n: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="market" stroke={MUTED} fontSize={11} tickLine={false} />
        <YAxis stroke={MUTED} fontSize={11} unit="%" domain={[0, 100]} tickLine={false} />
        <Tooltip {...tip} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="avg" name="Avg predicted" fill={SKY} radius={[4, 4, 0, 0]} />
        <Bar dataKey="hit" name="Actual hit rate" fill={NEON} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
