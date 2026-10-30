import { TopList } from "@/components/TopList";
import { Card, Empty, ErrorState } from "@/components/ui";
import { tryApi, userTz } from "@/lib/api";
import { LEAGUE_ORDER, longDate, todayIn } from "@/lib/format";
import type { League, TopItem } from "@/lib/types";

export const metadata = { title: "Today's Top Predictions" };

const MARKETS = [
  ["", "All markets"], ["1X2", "1X2"], ["BTTS", "BTTS"], ["OVER_1.5", "Over 1.5"],
  ["OVER_2.5", "Over 2.5"], ["UNDER_2.5", "Under 2.5"], ["OVER_3.5", "Over 3.5"],
] as const;

type SP = { market?: string; league?: string; min?: string; date?: string };

export default async function Predictions({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const tz = await userTz();
  const date = sp.date && /^\d{4}-\d{2}-\d{2}$/.test(sp.date) ? sp.date : todayIn(tz);
  const min = Math.min(Math.max(Number(sp.min ?? 0) || 0, 0), 95);
  const q = new URLSearchParams({ date, tz, limit: "40", min_p: String(min / 100) });
  if (sp.market) q.set("market", sp.market);
  if (sp.league) q.set("league", sp.league);
  const [top, leagues] = await Promise.all([
    tryApi<{ items: TopItem[] }>(`/api/predictions/top?${q}`, 120),
    tryApi<League[]>("/api/leagues", 300),
  ]);
  const sel = "h-9 rounded-lg border border-line/70 bg-card px-2 text-sm focus:border-neon/60 focus:outline-none";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold sm:text-3xl">Today&apos;s Top Predictions</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          {longDate(date)}. Ranked by modeled probability, weighted by data completeness, historical calibration for that league and market,
          and rating uncertainty. A high probability is not the same as a profitable bet — bookmaker prices already reflect likely outcomes.
        </p>
      </div>

      <Card>
        <form method="get" className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted">Market<br />
            <select name="market" defaultValue={sp.market ?? ""} className={sel}>{MARKETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label className="text-xs text-muted">League<br />
            <select name="league" defaultValue={sp.league ?? ""} className={sel}>
              <option value="">All leagues</option>
              {LEAGUE_ORDER.map((s) => leagues.data?.find((l) => l.slug === s)).filter(Boolean).map((l) => <option key={l!.slug} value={l!.slug}>{l!.name}</option>)}
            </select>
          </label>
          <label className="text-xs text-muted">Minimum probability<br />
            <select name="min" defaultValue={String(min)} className={sel}>{[0, 50, 55, 60, 65, 70, 75, 80].map((m) => <option key={m} value={m}>{m ? `${m}%+` : "Any"}</option>)}</select>
          </label>
          <label className="text-xs text-muted">Match date<br />
            <input type="date" name="date" defaultValue={date} className={sel} />
          </label>
          <button className="h-9 rounded-lg bg-neon px-4 text-sm font-semibold text-bg">Apply</button>
        </form>
      </Card>

      {top.error && <ErrorState message={top.error} />}
      {top.data && (top.data.items.length ? <TopList items={top.data.items} tz={tz} /> : <Empty>No upcoming predictions match these filters.</Empty>)}
    </div>
  );
}
