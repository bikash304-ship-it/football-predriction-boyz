import Link from "next/link";
import { notFound } from "next/navigation";
import { CheckCircle2, CircleDashed, Info } from "lucide-react";
import { GoalsDistChart, ProbHistoryChart, TeamCompareChart } from "@/components/charts";
import { AutoRefresh, WatchButton } from "@/components/client";
import { Card, ConfidenceBadge, Crest, DemoTag, ErrorState, Flag, ProbBar, SectionTitle, SplitBar, StatusPill } from "@/components/ui";
import { ApiError, api, userTz } from "@/lib/api";
import { FINAL, LIVE, dateTime, kickoffDate, kickoffTime, marketLabel, pct } from "@/lib/format";
import type { FixtureDetail, Prediction, Sentence, Split } from "@/lib/types";
import { StandingsTable } from "@/components/StandingsTable";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  try {
    const d = await api<FixtureDetail>(`/api/fixtures/${(await params).id}`, 60);
    return { title: `${d.fixture.home.name} vs ${d.fixture.away.name}` };
  } catch {
    return { title: "Match" };
  }
}

const SECTIONS: { key: keyof NonNullable<FixtureDetail["explanation"]>["sections"]; title: string }[] = [
  { key: "home_case", title: "Why the home team might win" },
  { key: "away_case", title: "Why the away team might win" },
  { key: "draw", title: "How likely is a draw" },
  { key: "btts", title: "Will both teams score" },
  { key: "goals", title: "Many goals or few" },
  { key: "key_stats", title: "Key supporting statistics" },
  { key: "risks", title: "What could make this wrong" },
];

function SentenceRow({ s }: { s: Sentence }) {
  return (
    <li className="flex gap-2">
      <span className={`mt-0.5 shrink-0 rounded px-1 text-[9px] font-bold uppercase leading-4 tracking-wider ${s.kind === "fact" ? "bg-sky/15 text-sky" : "bg-neon/15 text-neon"}`}
        title={s.kind === "fact" ? "Verified statistic retrieved from the data provider" : "Estimate produced by the statistical model"}>
        {s.kind === "fact" ? "Fact" : "Model"}
      </span>
      <span>{s.text}</span>
    </li>
  );
}

function FormStrip({ form }: { form: string }) {
  return (
    <span className="flex gap-1">
      {form.split("").map((c, i) => (
        <span key={i} className={`grid h-5 w-5 place-items-center rounded text-[10px] font-bold ${c === "W" ? "bg-neon/20 text-neon" : c === "D" ? "bg-muted/20 text-muted" : "bg-bad/20 text-bad"}`}>{c}</span>
      ))}
      {!form && <span className="text-xs text-muted">—</span>}
    </span>
  );
}

function SplitTable({ title, home, away, hName, aName }: { title: string; home: Split; away: Split; hName: string; aName: string }) {
  const row = (label: string, h: string, a: string) => (
    <tr className="border-t border-line/40"><td className="py-1.5 text-muted">{label}</td><td className="num text-right">{h}</td><td className="num text-right">{a}</td></tr>
  );
  const f = (x: number | null) => (x === null ? "—" : x.toFixed(2));
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-[11px] text-muted"><th className="py-1 text-left font-medium">{title}</th><th className="text-right font-semibold text-neon">{hName}</th><th className="text-right font-semibold text-sky">{aName}</th></tr></thead>
      <tbody>
        {row("Played", String(home.played), String(away.played))}
        {row("W-D-L", `${home.wins}-${home.draws}-${home.losses}`, `${away.wins}-${away.draws}-${away.losses}`)}
        {row("Goals for / match", f(home.gf_per_match), f(away.gf_per_match))}
        {row("Goals against / match", f(home.ga_per_match), f(away.ga_per_match))}
        {row("xG for / against", home.xg_for_per_match === null ? "n/a" : `${f(home.xg_for_per_match)} / ${f(home.xg_against_per_match)}`, away.xg_for_per_match === null ? "n/a" : `${f(away.xg_for_per_match)} / ${f(away.xg_against_per_match)}`)}
        {row("BTTS", pct(home.btts_rate), pct(away.btts_rate))}
        {row("Over 1.5 / 2.5 / 3.5", `${pct(home.over15_rate)} / ${pct(home.over25_rate)} / ${pct(home.over35_rate)}`, `${pct(away.over15_rate)} / ${pct(away.over25_rate)} / ${pct(away.over35_rate)}`)}
        {row("Clean sheets", pct(home.clean_sheet_rate), pct(away.clean_sheet_rate))}
      </tbody>
    </table>
  );
}

function ScoreHeatmap({ m, home, away }: { m: number[][]; home: string; away: string }) {
  const max = Math.max(...m.flat());
  return (
    <div className="overflow-x-auto">
      <div className="text-center text-[11px] text-sky">{away} goals →</div>
      <div className="mt-1 flex">
        <div className="flex items-center pr-1 text-[11px] text-neon [writing-mode:vertical-rl] rotate-180">{home} goals →</div>
        <div className="grid flex-1 gap-0.5" style={{ gridTemplateColumns: `24px repeat(${m.length}, minmax(34px, 1fr))` }}>
          <div />
          {m[0].map((_, j) => <div key={j} className="text-center text-[10px] text-muted">{j}</div>)}
          {m.map((r, i) => (
            <div key={i} className="contents">
              <div className="grid place-items-center text-[10px] text-muted">{i}</div>
              {r.map((p, j) => (
                <div key={j} title={`${i}-${j}: ${(p * 100).toFixed(1)}%`}
                  className={`num grid h-8 place-items-center rounded text-[10px] ${p / max > 0.55 ? "text-bg font-semibold" : "text-ink/80"}`}
                  style={{ background: `rgb(var(${i > j ? "--neon" : i < j ? "--sky" : "--muted"}) / ${0.08 + 0.92 * (p / max)})` }}>
                  {(p * 100).toFixed(p >= 0.1 ? 0 : 1)}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Markets({ p }: { p: Prediction }) {
  const lines = ["0.5", "1.5", "2.5", "3.5", "4.5"];
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 text-xs font-semibold text-muted">1X2 · Full-time result</div>
        <ProbBar {...p.display["1x2"]} />
        <div className="num mt-2 grid grid-cols-3 gap-2 text-center text-[11px] text-muted">
          {(["home", "draw", "away"] as const).map((k) => (
            <div key={k}>80% range {pct(p.uncertainty[k][0])}–{pct(p.uncertainty[k][1])}</div>
          ))}
        </div>
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold text-muted">BTTS · Both teams to score</div>
        <SplitBar left={p.display.btts.yes} right={p.display.btts.no} leftLabel="Yes" rightLabel="No" />
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold text-muted">Over / Under goals</div>
        <div className="space-y-2.5">
          {lines.map((l) => (
            <div key={l} className="grid grid-cols-[44px_1fr] items-center gap-3">
              <span className="num text-xs font-semibold">{l}</span>
              <SplitBar left={p.display.ou[l].over} right={p.display.ou[l].under} leftLabel="Over" rightLabel="Under" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const tz = await userTz();
  let d: FixtureDetail;
  try {
    d = await api<FixtureDetail>(`/api/fixtures/${id}`, 30);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof Error ? e.message : "Unknown error"} />;
  }
  const f = d.fixture;
  const p = d.prediction;
  const ex = d.explanation;
  const live = LIVE.has(f.status);
  const started = live || FINAL.has(f.status);
  const hp = p?.context.home_profile;
  const ap = p?.context.away_profile;

  return (
    <div className="space-y-6">
      <AutoRefresh seconds={live ? 45 : 300} />
      {/* Header */}
      <section className="relative overflow-hidden rounded-3xl border border-line/60 bg-gradient-to-br from-card to-bg p-5 sm:p-8">
        <div className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full bg-neon/10 blur-3xl" />
        <div className="pointer-events-none absolute -right-24 -bottom-24 h-64 w-64 rounded-full bg-sky/10 blur-3xl" />
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
          <Link href={`/leagues/${f.league_slug}`} className="flex items-center gap-1.5 hover:text-ink"><Flag code={f.country_code} /> {f.league_name}{f.round && ` · ${f.round}`}</Link>
          <span className="flex items-center gap-2">{d.demo && <DemoTag />}<StatusPill status={f.status} elapsed={f.elapsed} /><WatchButton id={f.id} /></span>
        </div>
        <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-6">
          <div className="flex flex-col items-center gap-2 text-center sm:flex-row sm:justify-end sm:text-right">
            <span className="order-2 font-display text-lg font-bold sm:order-1 sm:text-2xl">{f.home.name}</span>
            <span className="order-1 sm:order-2"><Crest team={f.home} size={56} /></span>
          </div>
          <div className="num text-center font-display">
            {started ? <div className="text-4xl font-bold sm:text-5xl">{f.score.home}<span className="mx-2 text-muted">–</span>{f.score.away}</div>
              : <div><div className="text-3xl font-bold sm:text-4xl">{kickoffTime(f.kickoff_utc, tz)}</div><div className="text-xs text-muted">{kickoffDate(f.kickoff_utc, tz)}</div></div>}
          </div>
          <div className="flex flex-col items-center gap-2 text-center sm:flex-row sm:text-left">
            <Crest team={f.away} size={56} />
            <span className="font-display text-lg font-bold sm:text-2xl">{f.away.name}</span>
          </div>
        </div>
        <div className="mt-4 text-center text-xs text-muted">{[f.venue, f.city].filter(Boolean).join(", ")} · {tz}</div>
      </section>

      {!p ? (
        <Card><p className="text-sm text-muted">No pre-match prediction is available for this fixture. Predictions are only published when the model has enough verified history, and never for postponed or cancelled matches.</p></Card>
      ) : (
        <>
          {/* Probabilities + xG */}
          <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
            <Card>
              <SectionTitle right={<ConfidenceBadge level={p.confidence} />}>Model probabilities</SectionTitle>
              <Markets p={p} />
              <p className="mt-4 flex items-start gap-1.5 text-[11px] text-muted"><Info size={13} className="mt-px shrink-0" />
                All markets derive from one score distribution (expected goals {p.rates.home.toFixed(2)} – {p.rates.away.toFixed(2)}), so they can&apos;t contradict each other. Estimates, not guarantees.</p>
            </Card>
            <div className="space-y-4">
              <Card>
                <SectionTitle>Expected goals & likeliest scores</SectionTitle>
                <div className="num grid grid-cols-2 gap-3 text-center">
                  <div className="rounded-xl bg-neon/10 p-3"><div className="text-[11px] text-muted">{f.home.name}</div><div className="font-display text-2xl font-bold text-neon">{p.rates.home.toFixed(2)}</div></div>
                  <div className="rounded-xl bg-sky/10 p-3"><div className="text-[11px] text-muted">{f.away.name}</div><div className="font-display text-2xl font-bold text-sky">{p.rates.away.toFixed(2)}</div></div>
                </div>
                <ol className="mt-3 grid grid-cols-3 gap-2">
                  {p.markets.top_scores.map((s, i) => (
                    <li key={s.score} className="rounded-xl border border-line/60 bg-card2/60 p-2 text-center">
                      <div className="text-[10px] text-muted">#{i + 1}</div>
                      <div className="num font-display text-lg font-bold">{s.score}</div>
                      <div className="num text-xs text-muted">{pct(s.p, 1)}</div>
                    </li>
                  ))}
                </ol>
              </Card>
              <Card>
                <SectionTitle>Total goals distribution</SectionTitle>
                <GoalsDistChart dist={p.markets.total_goals_dist} expected={p.rates.home + p.rates.away} />
              </Card>
            </div>
          </section>

          {/* Explanation */}
          {ex && (
            <Card>
              <SectionTitle right={<span className="text-[11px] text-muted">{ex.source === "deterministic" ? "Generated from model outputs" : "Model outputs, LLM-polished & number-checked"}</span>}>AI explanation</SectionTitle>
              <p className="font-display text-lg font-semibold">{ex.headline}.</p>
              {ex.summary && <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink/90">{ex.summary}</p>}
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {SECTIONS.map((s) => (
                  <div key={s.key} className="rounded-xl border border-line/50 bg-card2/40 p-4">
                    <h3 className="mb-2 text-sm font-semibold">{s.title}</h3>
                    <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink/90">{ex.sections[s.key].map((x, i) => <SentenceRow key={i} s={x} />)}</ul>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Score matrix + comparison */}
          <section className="grid gap-4 lg:grid-cols-2">
            <Card>
              <SectionTitle>Predicted score distribution (%)</SectionTitle>
              <ScoreHeatmap m={p.score_matrix} home={f.home.name} away={f.away.name} />
            </Card>
            {hp && ap && (
              <Card>
                <SectionTitle>Team comparison · last 10</SectionTitle>
                <TeamCompareChart home={f.home.name} away={f.away.name} rows={[
                  { metric: "Goals for / gm", home: hp.last10.gf_per_match, away: ap.last10.gf_per_match },
                  { metric: "Goals agst / gm", home: hp.last10.ga_per_match, away: ap.last10.ga_per_match },
                  { metric: "xG for / gm", home: hp.last10.xg_for_per_match, away: ap.last10.xg_for_per_match },
                  { metric: "Points / gm", home: hp.last10.played ? (hp.last10.wins * 3 + hp.last10.draws) / hp.last10.played : null, away: ap.last10.played ? (ap.last10.wins * 3 + ap.last10.draws) / ap.last10.played : null },
                ]} />
              </Card>
            )}
          </section>

          {hp && ap && (
            <section className="grid gap-4 lg:grid-cols-2">
              <Card>
                <SectionTitle>Recent form</SectionTitle>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between"><span className="flex items-center gap-2"><Crest team={f.home} size={20} />{f.home.name}</span><FormStrip form={hp.last5.form} /></div>
                  <div className="flex items-center justify-between"><span className="flex items-center gap-2"><Crest team={f.away} size={20} />{f.away.name}</span><FormStrip form={ap.last5.form} /></div>
                  <p className="text-[11px] text-muted">Last five league matches, most recent first. Rest: {hp.rest_days?.toFixed(1) ?? "—"} vs {ap.rest_days?.toFixed(1) ?? "—"} days.</p>
                </div>
                <div className="mt-4"><SplitTable title="Last 5" home={hp.last5} away={ap.last5} hName={f.home.name} aName={f.away.name} /></div>
              </Card>
              <Card>
                <SectionTitle>Home vs away performance</SectionTitle>
                <SplitTable title={`${f.home.name} at home / ${f.away.name} away`} home={hp.home} away={ap.away} hName="Home" aName="Away" />
              </Card>
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-3">
            <Card>
              <SectionTitle>Head-to-head</SectionTitle>
              {p.context.h2h.length ? (
                <ul className="space-y-1.5 text-sm">{p.context.h2h.map((m) => (
                  <li key={m.date} className="flex justify-between gap-2"><span className="truncate">{m.home} <span className="num font-semibold">{m.home_goals}–{m.away_goals}</span> {m.away}</span><span className="shrink-0 text-xs text-muted">{m.date.slice(0, 10)}</span></li>
                ))}</ul>
              ) : <p className="text-sm text-muted">No meetings in the stored history.</p>}
              <p className="mt-3 text-[11px] text-muted">Head-to-head is shown for context; the model gives it no special weight.</p>
            </Card>
            <Card>
              <SectionTitle>Team news</SectionTitle>
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2">{p.context.injuries_status === "verified" ? <CheckCircle2 size={15} className="text-neon" /> : <CircleDashed size={15} className="text-warn" />}
                  Injuries & suspensions: <span className="font-semibold">{p.context.injuries_status === "verified" ? "verified" : "unavailable"}</span></div>
                {p.context.injuries?.length ? <ul className="ml-6 list-disc text-xs text-muted">{p.context.injuries.map((i) => <li key={i.player}>{i.player} ({i.team}) — {i.reason ?? i.type}</li>)}</ul> : null}
                <div className="flex items-center gap-2">{p.context.lineups_status === "confirmed" ? <CheckCircle2 size={15} className="text-neon" /> : <CircleDashed size={15} className="text-warn" />}
                  Starting lineups: <span className="font-semibold">{p.context.lineups_status}</span></div>
                {p.context.lineups && Object.values(p.context.lineups).map((l, i) => (
                  <p key={i} className="text-xs text-muted">{l.formation}: {l.start_xi.join(", ")}</p>
                ))}
              </div>
            </Card>
            <Card>
              <SectionTitle>Model & data</SectionTitle>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
                <dt className="text-muted">Model</dt><dd className="font-mono">{p.model_version}</dd>
                <dt className="text-muted">Calculated</dt><dd>{dateTime(p.created_at, tz)}</dd>
                <dt className="text-muted">Fitted on</dt><dd>{p.model_fit.n_matches} matches</dd>
                <dt className="text-muted">Data completeness</dt><dd>{Math.round(p.completeness.score * 100)}%</dd>
                <dt className="text-muted">Home advantage</dt><dd>×{Math.exp(p.rates.home_adv).toFixed(2)} goals</dd>
              </dl>
              {p.completeness.missing.length > 0 && (
                <ul className="mt-3 space-y-1 text-[11px] text-warn">{p.completeness.missing.map((m) => <li key={m}>• {m}</li>)}</ul>
              )}
              {p.adjustments.length > 0 && (
                <ul className="mt-2 space-y-1 text-[11px] text-muted">{p.adjustments.map((a) => <li key={a.reason}>Adjusted ×{a.factor.toFixed(2)}: {a.reason}</li>)}</ul>
              )}
            </Card>
          </section>

          {d.prediction_history.length > 1 && (
            <Card>
              <SectionTitle>How the prediction moved before kickoff</SectionTitle>
              <ProbHistoryChart points={d.prediction_history} />
            </Card>
          )}

          {d.settlement && (
            <Card>
              <SectionTitle>Settlement (official pre-match prediction)</SectionTitle>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {d.settlement.map((s) => (
                  <div key={s.market} className="flex items-center justify-between rounded-lg border border-line/50 bg-card2/50 px-3 py-2 text-xs">
                    <span>{marketLabel(s.market, s.selection, f.home.name, f.away.name)} <span className="text-muted">({pct(s.probability ?? s.p)})</span></span>
                    <span className={`font-bold uppercase ${s.outcome === "won" ? "text-neon" : s.outcome === "lost" ? "text-bad" : "text-warn"}`}>{s.outcome}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {d.standings.length > 0 && (
        <Card>
          <SectionTitle right={<Link href={`/leagues/${f.league_slug}`} className="text-xs text-neon hover:underline">Full league page</Link>}>League standings</SectionTitle>
          <StandingsTable rows={d.standings} highlight={[f.home.name, f.away.name]} />
        </Card>
      )}
    </div>
  );
}
