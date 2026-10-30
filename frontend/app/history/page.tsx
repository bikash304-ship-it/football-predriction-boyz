import Link from "next/link";
import { Card, DemoTag, Empty, ErrorState } from "@/components/ui";
import { tryApi, userTz } from "@/lib/api";
import { LEAGUE_ORDER, kickoffDate, marketLabel, pct } from "@/lib/format";
import type { HistoryRow, League } from "@/lib/types";

export const metadata = { title: "Prediction history" };

export default async function History({ searchParams }: { searchParams: Promise<{ league?: string; market?: string }> }) {
  const sp = await searchParams;
  const tz = await userTz();
  const q = new URLSearchParams({ limit: "300", ...(sp.league ? { league: sp.league } : {}), ...(sp.market ? { market: sp.market } : {}) });
  const [{ data, error }, leagues] = await Promise.all([tryApi<{ items: HistoryRow[] }>(`/api/history?${q}`, 300), tryApi<League[]>("/api/leagues", 300)]);
  const sel = "h-9 rounded-lg border border-line/70 bg-card px-2 text-sm";
  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold sm:text-3xl">Prediction history</h1>
        <p className="mt-1 text-sm text-muted">Original pre-match predictions, stored before kickoff and never edited, settled on the official 90-minute score.</p>
      </div>
      <Card>
        <form method="get" className="flex flex-wrap items-end gap-3">
          <select name="league" defaultValue={sp.league ?? ""} className={sel} aria-label="League">
            <option value="">All leagues</option>
            {LEAGUE_ORDER.map((s) => leagues.data?.find((l) => l.slug === s)).filter(Boolean).map((l) => <option key={l!.slug} value={l!.slug}>{l!.name}</option>)}
          </select>
          <select name="market" defaultValue={sp.market ?? ""} className={sel} aria-label="Market">
            <option value="">All markets</option>
            {["1X2", "BTTS", "OU0.5", "OU1.5", "OU2.5", "OU3.5", "OU4.5"].map((m) => <option key={m} value={m}>{m.replace("OU", "O/U ")}</option>)}
          </select>
          <button className="h-9 rounded-lg bg-neon px-4 text-sm font-semibold text-bg">Filter</button>
        </form>
      </Card>
      {error && <ErrorState message={error} />}
      {data && (data.items.length === 0 ? <Empty>No settled predictions yet.</Empty> : (
        <Card className="overflow-x-auto p-0 sm:p-0">
          <table className="w-full min-w-[640px] text-sm">
            <thead><tr className="text-left text-[11px] uppercase tracking-wider text-muted">
              <th className="px-4 py-3">Date</th><th>Match</th><th>Prediction</th><th className="text-right">Prob.</th><th className="text-right">Final</th><th className="px-4 text-right">Result</th>
            </tr></thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={`${r.fixture_id}-${r.market}`} className="border-t border-line/40 hover:bg-card2/40">
                  <td className="px-4 py-2 text-xs text-muted">{kickoffDate(r.kickoff_utc, tz)}</td>
                  <td><Link href={`/match/${r.fixture_id}`} className="hover:text-neon">{r.home} v {r.away}</Link> {r.demo && <DemoTag />}</td>
                  <td>{marketLabel(r.market, r.selection, r.home, r.away)}</td>
                  <td className="num text-right">{pct(r.probability)}</td>
                  <td className="num text-right">{r.final?.[0]}–{r.final?.[1]}</td>
                  <td className={`px-4 text-right text-xs font-bold uppercase ${r.outcome === "won" ? "text-neon" : r.outcome === "lost" ? "text-bad" : "text-warn"}`}>{r.outcome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}
