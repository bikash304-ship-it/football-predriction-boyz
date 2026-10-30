import Link from "next/link";
import { Suspense } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { tryApi } from "@/lib/api";
import { FLAGS, LEAGUE_ORDER, LIVE, longDate, shiftDay, todayIn } from "@/lib/format";
import type { Fixture, League } from "@/lib/types";
import { MatchCard } from "./MatchCard";
import { AutoRefresh, LeagueFilter, PredictionNotifier } from "./client";
import { Empty, ErrorState, Flag } from "./ui";

export async function DayView({ day, tz, league }: { day: string; tz: string; league?: string }) {
  const q = new URLSearchParams({ date: day, tz, ...(league ? { league } : {}) });
  const [{ data, error }, leagues] = await Promise.all([
    tryApi<{ date: string; fixtures: Fixture[] }>(`/api/fixtures?${q}`, 60),
    tryApi<League[]>("/api/leagues", 300),
  ]);
  const today = todayIn(tz);
  const anyLive = data?.fixtures.some((f) => LIVE.has(f.status));
  const groups = LEAGUE_ORDER.map((slug) => ({ slug, items: (data?.fixtures ?? []).filter((f) => f.league_slug === slug) }))
    .filter((g) => g.items.length);

  return (
    <div className="space-y-5">
      <AutoRefresh seconds={anyLive ? 45 : 300} />
      {data && (
        <PredictionNotifier stamps={data.fixtures.filter((f) => f.prediction).map((f) => ({
          id: f.id, label: `${f.home.name} vs ${f.away.name}`, updated: f.prediction!.updated_at,
        }))} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold sm:text-3xl">{longDate(day)}</h1>
          <p className="text-sm text-muted">
            {data ? `${data.fixtures.length} matches` : "—"} · times in {tz}
            {day === today && " · today"}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Link className="chip hover:text-ink" href={`/day/${shiftDay(day, -1)}${league ? `?league=${league}` : ""}`} aria-label="Previous day"><ChevronLeft size={14} /> Prev</Link>
          {day !== today && <Link className="chip hover:text-ink" href="/today">Today</Link>}
          <Link className="chip hover:text-ink" href={`/day/${shiftDay(day, 1)}${league ? `?league=${league}` : ""}`} aria-label="Next day">Next <ChevronRight size={14} /></Link>
        </div>
      </div>

      {leagues.data && (
        <Suspense fallback={null}>
          <LeagueFilter leagues={leagues.data.map((l) => ({ slug: l.slug, name: l.name, flag: FLAGS[l.country_code] ?? "" }))} />
        </Suspense>
      )}

      {error && <ErrorState message={error} />}
      {data && groups.length === 0 && <Empty>No fixtures in the six covered leagues on this date{league ? " for this league" : ""}.</Empty>}

      {groups.map((g) => (
        <section key={g.slug}>
          <div className="mb-2 flex items-center gap-2">
            <Flag code={g.items[0].country_code} />
            <Link href={`/leagues/${g.slug}`} className="font-display font-semibold hover:text-neon">{g.items[0].league_name}</Link>
            <span className="text-xs text-muted">{g.items.length}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {g.items.map((f) => <MatchCard key={f.id} f={f} tz={tz} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
