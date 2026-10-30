import { notFound } from "next/navigation";
import { MatchCard } from "@/components/MatchCard";
import { StandingsTable } from "@/components/StandingsTable";
import { AutoRefresh } from "@/components/client";
import { Card, DemoTag, Empty, ErrorState, Flag, SectionTitle } from "@/components/ui";
import { ApiError, api, userTz } from "@/lib/api";
import { FINAL, LIVE } from "@/lib/format";
import type { Fixture, League, StandingRow } from "@/lib/types";

type LeaguePayload = { league: League; standings: StandingRow[]; fixtures: Fixture[]; demo: boolean };

export default async function LeaguePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const tz = await userTz();
  let d: LeaguePayload;
  try {
    d = await api<LeaguePayload>(`/api/leagues/${slug}`, 120);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof Error ? e.message : "Unknown error"} />;
  }
  const upcoming = d.fixtures.filter((f) => !FINAL.has(f.status));
  const results = d.fixtures.filter((f) => FINAL.has(f.status)).reverse();
  const groups = Array.from(new Set(d.standings.map((s) => s.group_name ?? "")));

  // Team statistics from the standings (verified table data).
  const attack = [...d.standings].sort((a, b) => b.goals_for / Math.max(b.played, 1) - a.goals_for / Math.max(a.played, 1)).slice(0, 5);
  const defence = [...d.standings].sort((a, b) => a.goals_against / Math.max(a.played, 1) - b.goals_against / Math.max(b.played, 1)).slice(0, 5);

  return (
    <div className="space-y-6">
      <AutoRefresh seconds={d.fixtures.some((f) => LIVE.has(f.status)) ? 45 : 300} />
      <div className="flex items-center gap-3">
        <Flag code={d.league.country_code} className="text-3xl" />
        <div>
          <h1 className="font-display text-2xl font-bold sm:text-3xl">{d.league.name} {d.demo && <DemoTag />}</h1>
          <p className="text-sm text-muted">{d.league.country}</p>
        </div>
      </div>

      <section className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card>
          <SectionTitle>Standings</SectionTitle>
          {d.standings.length === 0 ? <p className="text-sm text-muted">Standings not available yet.</p> :
            groups.map((g) => (
              <div key={g} className="mb-4 last:mb-0">
                {g && <div className="mb-1 text-xs font-semibold text-sky">{g}</div>}
                <StandingsTable rows={d.standings.filter((s) => (s.group_name ?? "") === g)} />
              </div>
            ))}
        </Card>
        <div className="space-y-4">
          <Card>
            <SectionTitle>Best attacks · goals per game</SectionTitle>
            <ul className="space-y-1.5 text-sm">{attack.map((s) => <li key={s.team} className="flex justify-between"><span>{s.team}</span><span className="num font-semibold text-neon">{(s.goals_for / Math.max(s.played, 1)).toFixed(2)}</span></li>)}</ul>
          </Card>
          <Card>
            <SectionTitle>Best defences · conceded per game</SectionTitle>
            <ul className="space-y-1.5 text-sm">{defence.map((s) => <li key={s.team} className="flex justify-between"><span>{s.team}</span><span className="num font-semibold text-sky">{(s.goals_against / Math.max(s.played, 1)).toFixed(2)}</span></li>)}</ul>
          </Card>
        </div>
      </section>

      <section>
        <SectionTitle>Fixtures & predictions</SectionTitle>
        {upcoming.length ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{upcoming.map((f) => <MatchCard key={f.id} f={f} tz={tz} showDate />)}</div>
          : <Empty>No upcoming fixtures in the next eight days.</Empty>}
      </section>
      {results.length > 0 && (
        <section>
          <SectionTitle>Recent results</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{results.slice(0, 9).map((f) => <MatchCard key={f.id} f={f} tz={tz} showDate />)}</div>
        </section>
      )}
    </div>
  );
}
