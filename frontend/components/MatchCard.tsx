import Link from "next/link";
import { FINAL, LIVE, kickoffTime, kickoffDate, marketLabel } from "@/lib/format";
import type { Fixture } from "@/lib/types";
import { ConfidenceBadge, Crest, DemoTag, Flag, ProbBar, StatusPill } from "./ui";
import { WatchButton } from "./client";

export function MatchCard({ f, tz, showDate = false }: { f: Fixture; tz: string; showDate?: boolean }) {
  const p = f.prediction;
  const started = LIVE.has(f.status) || FINAL.has(f.status);
  const pick = p?.top_pick;
  return (
    <Link
      href={`/match/${f.id}`}
      className="glass group block animate-rise p-4 transition hover:border-neon/50 hover:shadow-glow focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
    >
      <div className="mb-3 flex items-center justify-between gap-2 text-[11px] text-muted">
        <span className="flex min-w-0 items-center gap-1.5 truncate">
          <Flag code={f.country_code} /> <span className="truncate">{f.league_name}</span>
          {f.round && <span className="hidden truncate opacity-70 sm:inline">· {f.round}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          {f.demo && <DemoTag />}
          <StatusPill status={f.status} elapsed={f.elapsed} />
          <WatchButton id={f.id} />
        </span>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Crest team={f.home} />
          <span className="truncate text-sm font-semibold">{f.home.name}</span>
        </div>
        <div className="num text-center font-display">
          {started ? (
            <span className="text-xl font-bold">{f.score.home ?? 0}<span className="mx-1 text-muted">–</span>{f.score.away ?? 0}</span>
          ) : (
            <span className="text-sm font-semibold text-ink">
              {showDate && <span className="block text-[10px] font-normal text-muted">{kickoffDate(f.kickoff_utc, tz)}</span>}
              {kickoffTime(f.kickoff_utc, tz)}
            </span>
          )}
        </div>
        <div className="flex min-w-0 items-center justify-end gap-2">
          <span className="truncate text-right text-sm font-semibold">{f.away.name}</span>
          <Crest team={f.away} />
        </div>
      </div>

      {p ? (
        <div className="mt-4 space-y-3">
          <ProbBar {...p["1x2"]} />
          <div className="num grid grid-cols-3 gap-2 text-center text-[11px]">
            <div className="rounded-lg bg-card2/70 px-2 py-1.5"><div className="text-muted">BTTS Yes</div><div className="font-semibold">{p.btts.yes}%</div></div>
            <div className="rounded-lg bg-card2/70 px-2 py-1.5"><div className="text-muted">Over 2.5</div><div className="font-semibold">{p.ou25.over}%</div></div>
            <div className="rounded-lg bg-card2/70 px-2 py-1.5"><div className="text-muted">xG</div><div className="font-semibold">{p.xg.home.toFixed(2)}–{p.xg.away.toFixed(2)}</div></div>
          </div>
          <div className="flex items-center justify-between gap-2 text-[11px]">
            <span className="truncate text-muted">
              Most probable: <span className="font-semibold text-ink">{marketLabel(pick!.market, pick!.selection, f.home.name, f.away.name)}</span>
            </span>
            <ConfidenceBadge level={p.confidence} />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted">
          {f.status === "PST" || f.status === "CANC" ? "No prediction — fixture not being played as scheduled." : "Prediction not yet available (insufficient verified data or not yet computed)."}
        </p>
      )}
    </Link>
  );
}
