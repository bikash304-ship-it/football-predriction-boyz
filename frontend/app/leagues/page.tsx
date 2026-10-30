import Link from "next/link";
import { Card, ErrorState, Flag } from "@/components/ui";
import { tryApi } from "@/lib/api";
import { LEAGUE_ORDER } from "@/lib/format";
import type { League } from "@/lib/types";

export const metadata = { title: "Leagues" };

export default async function Leagues() {
  const { data, error } = await tryApi<League[]>("/api/leagues", 300);
  if (error) return <ErrorState message={error} />;
  const leagues = LEAGUE_ORDER.map((s) => data!.find((l) => l.slug === s)).filter(Boolean) as League[];
  return (
    <div className="space-y-5">
      <h1 className="font-display text-2xl font-bold sm:text-3xl">Leagues</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {leagues.map((l) => (
          <Link key={l.slug} href={`/leagues/${l.slug}`}>
            <Card className="flex items-center gap-4 transition hover:border-neon/50 hover:shadow-glow">
              {l.logo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={l.logo} alt="" width={44} height={44} className="object-contain" />
              ) : (
                <Flag code={l.country_code} className="text-4xl" />
              )}
              <div className="min-w-0">
                <div className="font-display text-lg font-bold">{l.name}</div>
                <div className="text-xs text-muted">{l.country} · {l.today} match{l.today === 1 ? "" : "es"} today</div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
