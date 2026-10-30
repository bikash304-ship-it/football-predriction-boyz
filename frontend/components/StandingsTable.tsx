import type { StandingRow } from "@/lib/types";
import { Crest } from "./ui";

export function StandingsTable({ rows, highlight = [] }: { rows: StandingRow[]; highlight?: string[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead><tr className="text-left text-[11px] uppercase tracking-wider text-muted">
          <th className="py-2 pr-2">#</th><th>Team</th><th className="num text-right">P</th><th className="num text-right">W</th><th className="num text-right">D</th><th className="num text-right">L</th><th className="num text-right">GD</th><th className="num text-right">Pts</th><th className="pl-3">Form</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.group_name ?? ""}-${r.team}`} className={`border-t border-line/40 ${highlight.includes(r.team) ? "bg-neon/5" : ""}`}>
              <td className="num py-2 pr-2 text-muted">{r.rank}</td>
              <td className="flex items-center gap-2 py-2"><Crest team={{ name: r.team, logo: r.logo ?? null, initials: r.initials }} size={20} /><span className={highlight.includes(r.team) ? "font-semibold" : ""}>{r.team}</span></td>
              <td className="num text-right">{r.played}</td><td className="num text-right">{r.won}</td><td className="num text-right">{r.drawn}</td><td className="num text-right">{r.lost}</td>
              <td className="num text-right">{r.goals_for - r.goals_against > 0 ? "+" : ""}{r.goals_for - r.goals_against}</td>
              <td className="num text-right font-bold">{r.points}</td>
              <td className="pl-3 font-mono text-xs text-muted">{r.form ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
