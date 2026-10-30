import Link from "next/link";
import type { ReactNode } from "react";
import { FLAGS, statusLabel } from "@/lib/format";
import type { Team } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass p-4 sm:p-5 ${className}`}>{children}</div>;
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <h2 className="h-section">{children}</h2>
      {right}
    </div>
  );
}

export function Crest({ team, size = 28 }: { team: Pick<Team, "name" | "logo" | "initials">; size?: number }) {
  if (team.logo) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={team.logo} alt="" width={size} height={size} className="shrink-0 object-contain" loading="lazy" />;
  }
  // Placeholder crest (demo clubs / missing provider logo): initials on a shield.
  return (
    <span
      aria-hidden
      style={{ width: size, height: size, fontSize: size * 0.34 }}
      className="grid shrink-0 place-items-center rounded-[30%_30%_45%_45%] border border-line bg-card2 font-display font-bold text-muted"
    >
      {team.initials}
    </span>
  );
}

export function Flag({ code, className = "" }: { code: string; className?: string }) {
  return <span className={className} aria-hidden>{FLAGS[code] ?? "🏳️"}</span>;
}

export function StatusPill({ status, elapsed }: { status: string; elapsed: number | null }) {
  const s = statusLabel(status, elapsed);
  const tone = {
    live: "border-bad/50 bg-bad/10 text-bad",
    final: "border-line bg-card2 text-muted",
    void: "border-warn/50 bg-warn/10 text-warn",
    upcoming: "border-sky/40 bg-sky/10 text-sky",
  }[s.tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tone}`}>
      {s.tone === "live" && <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-bad" />}
      {s.text}
    </span>
  );
}

export function ConfidenceBadge({ level }: { level: string }) {
  const tone = level === "High" ? "text-neon border-neon/40 bg-neon/10" : level === "Medium" ? "text-sky border-sky/40 bg-sky/10" : "text-warn border-warn/40 bg-warn/10";
  return <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${tone}`}>{level} confidence</span>;
}

export function DemoTag() {
  return <span className="demo-tag" title="Demo data: fictional clubs, simulated results">Demo</span>;
}

/** Three-segment 1X2 bar. Widths are the model's integer percentages (sum to 100). */
export function ProbBar({ home, draw, away, labels = true }: { home: number; draw: number; away: number; labels?: boolean }) {
  const max = Math.max(home, draw, away);
  const seg = (v: number, color: string) => (
    <div style={{ width: `${v}%` }} className={`h-full ${color} ${v === max ? "opacity-100" : "opacity-45"} transition-[width] duration-500`} />
  );
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-card2" role="img" aria-label={`Home ${home}%, draw ${draw}%, away ${away}%`}>
        {seg(home, "bg-neon")}
        {seg(draw, "bg-muted")}
        {seg(away, "bg-sky")}
      </div>
      {labels && (
        <div className="num mt-1.5 flex justify-between text-[11px] text-muted">
          <span className={home === max ? "font-semibold text-neon" : ""}>1 · {home}%</span>
          <span className={draw === max ? "font-semibold text-ink" : ""}>X · {draw}%</span>
          <span className={away === max ? "font-semibold text-sky" : ""}>2 · {away}%</span>
        </div>
      )}
    </div>
  );
}

/** Two-way market bar (BTTS Yes/No, Over/Under). */
export function SplitBar({ left, right, leftLabel, rightLabel }: { left: number; right: number; leftLabel: string; rightLabel: string }) {
  const lMax = left >= right;
  return (
    <div>
      <div className="num mb-1 flex justify-between text-xs">
        <span className={lMax ? "font-semibold text-neon" : "text-muted"}>{leftLabel} {left}%</span>
        <span className={!lMax ? "font-semibold text-sky" : "text-muted"}>{rightLabel} {right}%</span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-card2">
        <div style={{ width: `${left}%` }} className={`h-full bg-neon ${lMax ? "" : "opacity-40"}`} />
        <div style={{ width: `${right}%` }} className={`h-full bg-sky ${!lMax ? "" : "opacity-40"}`} />
      </div>
    </div>
  );
}

export function ErrorState({ message, timestamp }: { message: string; timestamp?: string }) {
  return (
    <div className="glass border-bad/40 p-5 text-sm">
      <div className="font-semibold text-bad">Data temporarily unavailable</div>
      <p className="mt-1 text-muted">{message}</p>
      {timestamp && <p className="mt-1 text-xs text-muted">Last verified update: {timestamp}</p>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="glass p-6 text-center text-sm text-muted">{children}</div>;
}

export function Tabs({ items, active }: { items: { href: string; label: string }[]; active: string }) {
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-1">
      {items.map((i) => (
        <Link key={i.href} href={i.href} className={`chip whitespace-nowrap ${active === i.href ? "chip-on" : "hover:text-ink"}`}>
          {i.label}
        </Link>
      ))}
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="glass p-4">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</div>
      <div className="num mt-1 font-display text-2xl font-bold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}
