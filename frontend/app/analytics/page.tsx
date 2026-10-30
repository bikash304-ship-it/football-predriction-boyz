import { CalibrationChart, MarketBarChart } from "@/components/charts";
import { Card, DemoTag, Empty, ErrorState, SectionTitle, Stat } from "@/components/ui";
import { tryApi } from "@/lib/api";
import { pct } from "@/lib/format";
import type { Agg, Analytics, League } from "@/lib/types";

export const metadata = { title: "Analytics" };

const f3 = (x?: number | null) => (x === null || x === undefined ? "—" : x.toFixed(3));

function AggRow({ name, a }: { name: string; a: Agg }) {
  return (
    <tr className="border-t border-line/40">
      <td className="py-2">{name}</td>
      <td className="num text-right">{a.n}</td>
      <td className="num text-right">{pct(a.avg_probability)}</td>
      <td className="num text-right font-semibold">{pct(a.hit_rate)}</td>
      <td className="num text-right">{f3(a.brier)}</td>
      <td className="num text-right">{f3(a.log_loss)}</td>
      <td className="num text-right">{a.ece === null || a.ece === undefined ? "—" : pct(a.ece, 1)}</td>
    </tr>
  );
}

export default async function AnalyticsPage() {
  const [{ data, error }, leagues] = await Promise.all([tryApi<Analytics>("/api/analytics", 300), tryApi<League[]>("/api/leagues", 300)]);
  if (error) return <ErrorState message={error} />;
  const a = data!;
  const name = (slug: string) => leagues.data?.find((l) => l.slug === slug)?.name ?? slug;
  const head = (
    <thead><tr className="text-left text-[11px] uppercase tracking-wider text-muted">
      <th className="py-2"></th><th className="text-right">Settled</th><th className="text-right">Avg prob</th><th className="text-right">Hit rate</th>
      <th className="text-right">Brier</th><th className="text-right">Log loss</th><th className="text-right">Calib. err</th>
    </tr></thead>
  );
  const marketRows = Object.entries(a.by_market).filter(([, v]) => v.n).map(([m, v]) => ({
    market: m.replace("OU", "O/U "), hit: Math.round((v.hit_rate ?? 0) * 100), avg: Math.round((v.avg_probability ?? 0) * 100), n: v.n,
  }));
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold sm:text-3xl">Model performance {a.demo && <DemoTag />}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Every number here comes from settled, immutable pre-match predictions — the most probable selection in each market.
          Well-calibrated means the hit rate tracks the average predicted probability. {a.note}
        </p>
      </div>
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {(["7", "30", "90"] as const).map((w) => (
          <Stat key={w} label={`Last ${w} days`} value={pct(a.windows[w].hit_rate)} sub={`${a.windows[w].n} settled · avg prob ${pct(a.windows[w].avg_probability)} · Brier ${f3(a.windows[w].brier)}`} />
        ))}
      </section>
      {a.calibration ? (
        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <SectionTitle>Calibration · predicted vs observed</SectionTitle>
            <CalibrationChart bins={a.calibration} />
            <p className="text-[11px] text-muted">Points on the dashed line are perfectly calibrated. Bubble size = number of predictions.</p>
          </Card>
          <Card>
            <SectionTitle>By market · predicted vs actual</SectionTitle>
            <MarketBarChart rows={marketRows} />
          </Card>
        </section>
      ) : <Empty>No settled predictions yet — performance appears here after the first matches finish.</Empty>}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-x-auto">
          <SectionTitle>By league</SectionTitle>
          <table className="w-full min-w-[520px] text-sm">{head}<tbody>{Object.entries(a.by_league).map(([k, v]) => <AggRow key={k} name={name(k)} a={v} />)}</tbody></table>
        </Card>
        <Card className="overflow-x-auto">
          <SectionTitle>By market</SectionTitle>
          <table className="w-full min-w-[520px] text-sm">{head}<tbody>{Object.entries(a.by_market).map(([k, v]) => <AggRow key={k} name={k.replace("OU", "Over/Under ")} a={v} />)}</tbody></table>
        </Card>
      </section>
      {a.windows["90"].hypothetical_roi && (
        <Card>
          <SectionTitle>Hypothetical return (documented assumptions)</SectionTitle>
          <p className="text-sm text-muted">1 unit level stake on every settled pick that had a stored pre-kickoff decimal price from the first listed bookmaker; voids refunded; no commission.
            Result over 90 days: {a.windows["90"].hypothetical_roi.bets} bets, {a.windows["90"].hypothetical_roi.profit_units.toFixed(2)} units ({pct(a.windows["90"].hypothetical_roi.roi, 1)} ROI). Past results do not predict future returns.</p>
        </Card>
      )}
    </div>
  );
}
