import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MatchCard } from "@/components/MatchCard";
import { TopList } from "@/components/TopList";
import { AutoRefresh } from "@/components/client";
import { Card, Empty, ErrorState, Flag, SectionTitle, Stat } from "@/components/ui";
import { tryApi, userTz } from "@/lib/api";
import { FINAL, LEAGUE_ORDER, LIVE, longDate, relative, todayIn } from "@/lib/format";
import type { Fixture, League, TopItem } from "@/lib/types";

export default async function Home() {
  const tz = await userTz();
  const today = todayIn(tz);
  const [fx, lg, top] = await Promise.all([
    tryApi<{ fixtures: Fixture[] }>(`/api/fixtures?date=${today}&tz=${encodeURIComponent(tz)}`, 60),
    tryApi<League[]>("/api/leagues", 300),
    tryApi<{ items: TopItem[] }>(`/api/predictions/top?date=${today}&tz=${encodeURIComponent(tz)}&limit=6`, 120),
  ]);
  const all = fx.data?.fixtures ?? [];
  const live = all.filter((f) => LIVE.has(f.status));
  const upcoming = all.filter((f) => f.status === "NS" || f.status === "TBD");
  const done = all.filter((f) => FINAL.has(f.status));
  const withPred = all.filter((f) => f.prediction);
  const recent = [...withPred].sort((a, b) => b.prediction!.updated_at.localeCompare(a.prediction!.updated_at)).slice(0, 5);
  const highest = withPred.length
    ? Math.max(...withPred.map((f) => Math.max(f.prediction!["1x2"].home, f.prediction!["1x2"].draw, f.prediction!["1x2"].away)))
    : null;

  return (
    <div className="space-y-8">
      <AutoRefresh seconds={live.length ? 45 : 300} />
      <section className="relative overflow-hidden rounded-3xl border border-line/60 bg-gradient-to-br from-card via-card to-bg p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-neon/15 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-neon">{longDate(today)}</p>
        <h1 className="mt-2 max-w-2xl font-display text-3xl font-bold leading-tight sm:text-4xl">
          Smart Predictions. <span className="text-muted">Better Football Insights.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Every probability below comes from one Dixon-Coles score model per match, so 1X2, BTTS and Over/Under always agree with each other.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link href="/predictions" className="inline-flex items-center gap-1.5 rounded-xl bg-neon px-4 py-2 text-sm font-semibold text-bg shadow-glow">
            Today&apos;s Top Predictions <ArrowRight size={15} />
          </Link>
          <Link href="/today" className="inline-flex items-center gap-1.5 rounded-xl border border-line px-4 py-2 text-sm font-semibold hover:border-neon/60">All of today</Link>
        </div>
      </section>

      {fx.error && <ErrorState message={fx.error} />}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Matches today" value={fx.data ? all.length : "—"} sub={`${upcoming.length} upcoming`} />
        <Stat label="Live now" value={<span className={live.length ? "text-bad" : ""}>{live.length}</span>} sub="auto-refreshing" />
        <Stat label="Completed" value={done.length} sub="settled automatically" />
        <Stat label="Highest modeled 1X2" value={highest !== null ? `${highest}%` : "—"} sub="a probability, not a certainty" />
      </section>

      {lg.data && (
        <section>
          <SectionTitle>Matches by league today</SectionTitle>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {LEAGUE_ORDER.map((slug) => lg.data!.find((l) => l.slug === slug)).filter(Boolean).map((l) => (
              <Link key={l!.slug} href={`/today?league=${l!.slug}`} className="glass flex items-center justify-between gap-2 p-3 transition hover:border-neon/50">
                <span className="flex min-w-0 items-center gap-2 text-sm"><Flag code={l!.country_code} /><span className="truncate">{l!.name}</span></span>
                <span className="num font-display text-lg font-bold">{l!.today}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {live.length > 0 && (
        <section>
          <SectionTitle>Live matches</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{live.map((f) => <MatchCard key={f.id} f={f} tz={tz} />)}</div>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <SectionTitle right={<Link href="/predictions" className="text-xs text-neon hover:underline">See all</Link>}>Today&apos;s Top Predictions</SectionTitle>
          {top.data?.items.length ? <TopList items={top.data.items} tz={tz} /> : <Empty>No qualifying upcoming predictions today.</Empty>}
        </div>
        <div>
          <SectionTitle>Recently updated predictions</SectionTitle>
          <Card className="divide-y divide-line/50 p-0 sm:p-0">
            {recent.length ? recent.map((f) => (
              <Link key={f.id} href={`/match/${f.id}`} className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-card2/50">
                <span className="truncate">{f.home.name} <span className="text-muted">vs</span> {f.away.name}</span>
                <span className="shrink-0 text-xs text-muted">{relative(f.prediction!.updated_at)}</span>
              </Link>
            )) : <p className="p-4 text-sm text-muted">No predictions yet.</p>}
          </Card>
        </div>
      </section>

      {upcoming.length > 0 && (
        <section>
          <SectionTitle right={<Link href="/today" className="text-xs text-neon hover:underline">Full schedule</Link>}>Upcoming fixtures</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{upcoming.slice(0, 9).map((f) => <MatchCard key={f.id} f={f} tz={tz} />)}</div>
        </section>
      )}

      {done.length > 0 && (
        <section>
          <SectionTitle>Completed results</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{done.slice(0, 6).map((f) => <MatchCard key={f.id} f={f} tz={tz} />)}</div>
        </section>
      )}
    </div>
  );
}
