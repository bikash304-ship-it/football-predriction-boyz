import Link from "next/link";
import { kickoffTime, marketLabel } from "@/lib/format";
import type { TopItem } from "@/lib/types";
import { ConfidenceBadge, Crest, DemoTag, Flag } from "./ui";

export function TopList({ items, tz }: { items: TopItem[]; tz: string }) {
  return (
    <ol className="space-y-2">
      {items.map((it, i) => {
        const f = it.fixture;
        const pct = Math.round(it.p * 100);
        return (
          <li key={`${f.id}-${it.market}`}>
            <Link href={`/match/${f.id}`} className="glass flex items-center gap-3 p-3 transition hover:border-neon/50 sm:gap-4">
              <span className="num w-6 shrink-0 text-center font-display text-sm font-bold text-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[11px] text-muted">
                  <Flag code={f.country_code} /> {f.league_name} · {kickoffTime(f.kickoff_utc, tz)} {f.demo && <DemoTag />}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 truncate text-sm font-semibold">
                  <Crest team={f.home} size={18} /> {f.home.name} <span className="text-muted">v</span> {f.away.name} <Crest team={f.away} size={18} />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-ink">{marketLabel(it.market, it.selection, f.home.name, f.away.name)}</span>
                  <ConfidenceBadge level={it.confidence} />
                  <span className="text-muted">data {Math.round(it.completeness * 100)}%</span>
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="num font-display text-xl font-bold text-neon">{pct}%</div>
                <div className="text-[10px] text-muted">modeled</div>
              </div>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
