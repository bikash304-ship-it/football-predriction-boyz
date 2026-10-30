import { MatchCard } from "@/components/MatchCard";
import { Card, Crest, Empty, ErrorState, SectionTitle } from "@/components/ui";
import { tryApi, userTz } from "@/lib/api";
import type { Fixture, Team } from "@/lib/types";

export const metadata = { title: "Search" };

export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const tz = await userTz();
  if (q.trim().length < 2) return <Empty>Type at least two characters to search clubs and matches.</Empty>;
  const { data, error } = await tryApi<{ teams: Team[]; fixtures: Fixture[] }>(`/api/search?q=${encodeURIComponent(q)}`, 60);
  if (error) return <ErrorState message={error} />;
  return (
    <div className="space-y-5">
      <h1 className="font-display text-2xl font-bold">Results for “{q}”</h1>
      {data!.teams.length > 0 && (
        <Card>
          <SectionTitle>Clubs</SectionTitle>
          <ul className="flex flex-wrap gap-2">{data!.teams.map((t) => <li key={t.id} className="chip text-ink"><Crest team={t} size={18} />{t.name}</li>)}</ul>
        </Card>
      )}
      {data!.fixtures.length ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{data!.fixtures.map((f) => <MatchCard key={f.id} f={f} tz={tz} showDate />)}</div>
      ) : <Empty>No matches found for that search in the current window.</Empty>}
    </div>
  );
}
