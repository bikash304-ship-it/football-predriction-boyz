/** Time/date helpers. All kickoffs arrive as UTC ISO strings; Intl handles DST per zone. */

export function kickoffTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: tz }).format(new Date(iso));
}

export function kickoffDate(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: tz }).format(new Date(iso));
}

export function longDate(isoDay: string): string {
  const [y, m, d] = isoDay.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)));
}

export function dateTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: tz }).format(new Date(iso));
}

/** YYYY-MM-DD for "today" in a timezone. */
export function todayIn(tz: string, offsetDays = 0): string {
  const d = new Date(Date.now() + offsetDays * 86400000);
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return parts; // en-CA formats as YYYY-MM-DD
}

export function shiftDay(isoDay: string, delta: number): string {
  const [y, m, d] = isoDay.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + delta));
  return t.toISOString().slice(0, 10);
}

export function relative(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;

export const LIVE = new Set(["1H", "HT", "2H", "ET", "P", "INT", "SUSP"]);
export const FINAL = new Set(["FT", "AET", "PEN"]);
export const VOID = new Set(["PST", "CANC", "ABD", "AWD", "WO"]);

export function statusLabel(status: string, elapsed: number | null): { text: string; tone: "live" | "final" | "void" | "upcoming" } {
  if (LIVE.has(status)) return { text: status === "HT" ? "HT" : `${elapsed ?? ""}'`, tone: "live" };
  if (FINAL.has(status)) return { text: status === "FT" ? "FT" : status, tone: "final" };
  if (VOID.has(status)) return { text: { PST: "Postponed", CANC: "Cancelled", ABD: "Abandoned", AWD: "Awarded", WO: "Walkover" }[status] ?? status, tone: "void" };
  return { text: status === "TBD" ? "TBD" : "Upcoming", tone: "upcoming" };
}

export function marketLabel(market: string, selection: string, home?: string, away?: string): string {
  if (market === "1X2") return selection === "1" ? `${home ?? "Home"} win` : selection === "2" ? `${away ?? "Away"} win` : "Draw";
  if (market === "BTTS") return `Both teams to score: ${selection}`;
  if (market.startsWith("OU")) return `${selection} ${market.slice(2)} goals`;
  return `${market} ${selection}`;
}

export const FLAGS: Record<string, string> = {
  "GB-ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", ES: "🇪🇸", DE: "🇩🇪", FR: "🇫🇷", NO: "🇳🇴", US: "🇺🇸",
};

export const LEAGUE_ORDER = ["premier-league", "la-liga", "bundesliga", "ligue-1", "eliteserien", "mls"];
