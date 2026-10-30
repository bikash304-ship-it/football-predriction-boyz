"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { usePrefs } from "@/lib/prefs";

const LEAGUES = [
  ["premier-league", "Premier League"], ["la-liga", "La Liga"], ["bundesliga", "Bundesliga"],
  ["ligue-1", "Ligue 1"], ["eliteserien", "Eliteserien"], ["mls", "MLS"],
] as const;

const COMMON_TZ = ["Europe/Oslo", "Europe/London", "Europe/Madrid", "Europe/Berlin", "Europe/Paris", "America/New_York",
  "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Toronto", "Asia/Kathmandu", "Asia/Kolkata", "UTC"];

function Row({ title, hint, children, id }: { title: string; hint?: string; children: React.ReactNode; id?: string }) {
  return (
    <div id={id} className="grid gap-3 border-t border-line/50 py-5 first:border-t-0 first:pt-0 sm:grid-cols-[220px_1fr]">
      <div><div className="text-sm font-semibold">{title}</div>{hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}</div>
      <div>{children}</div>
    </div>
  );
}

export default function Settings() {
  const [prefs, update] = usePrefs();
  const [team, setTeam] = useState("");
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [zones, setZones] = useState<string[]>(COMMON_TZ);
  useEffect(() => {
    try {
      const all = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? [];
      if (all.length) setZones(Array.from(new Set([...COMMON_TZ, ...all])));
    } catch { /* keep the short list */ }
  }, []);

  const input = "h-9 rounded-lg border border-line/70 bg-card px-3 text-sm focus:border-neon/60 focus:outline-none";

  async function refresh(job: string) {
    setMsg("Running…");
    const r = await fetch(`/api/proxy/admin/refresh?job=${job}`, { method: "POST", headers: { "x-admin-token": token } }).catch(() => null);
    setMsg(!r ? "Backend unreachable." : r.ok ? `Queued: ${job}. Data will update shortly.` : r.status === 401 ? "Invalid admin token." : `Failed (HTTP ${r.status}).`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="font-display text-2xl font-bold sm:text-3xl">Settings</h1>
      <div className="glass p-5 sm:p-6">
        <Row title="Timezone" hint="Kickoff times convert automatically, including daylight saving.">
          <select value={prefs.tz} onChange={(e) => { update({ tz: e.target.value }); location.reload(); }} className={`${input} w-full sm:w-72`}>
            {zones.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </Row>
        <Row title="Appearance">
          <div className="flex gap-2">
            {(["dark", "light"] as const).map((t) => (
              <button key={t} onClick={() => update({ theme: t })} className={`chip capitalize ${prefs.theme === t ? "chip-on" : ""}`}>{t}</button>
            ))}
          </div>
        </Row>
        <Row title="Odds display" hint="Used when licensed bookmaker odds are enabled on the server.">
          <button className="chip chip-on">Decimal (e.g. 2.10)</button>
        </Row>
        <Row title="Favourite leagues">
          <div className="flex flex-wrap gap-2">
            {LEAGUES.map(([slug, name]) => {
              const on = prefs.favLeagues.includes(slug);
              return <button key={slug} onClick={() => update({ favLeagues: on ? prefs.favLeagues.filter((x) => x !== slug) : [...prefs.favLeagues, slug] })}
                className={`chip ${on ? "chip-on" : ""}`}>{name}</button>;
            })}
          </div>
        </Row>
        <Row title="Favourite teams">
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (team.trim()) { update({ favTeams: Array.from(new Set([...prefs.favTeams, team.trim()])) }); setTeam(""); } }}>
            <input value={team} onChange={(e) => setTeam(e.target.value)} placeholder="Club name" className={`${input} flex-1`} />
            <button className="h-9 rounded-lg bg-neon px-3 text-sm font-semibold text-bg">Add</button>
          </form>
          <div className="mt-2 flex flex-wrap gap-2">{prefs.favTeams.map((t) => (
            <span key={t} className="chip text-ink">
              <Link href={`/search?q=${encodeURIComponent(t)}`}>{t}</Link>
              <button aria-label={`Remove ${t}`} onClick={() => update({ favTeams: prefs.favTeams.filter((x) => x !== t) })}><Trash2 size={12} /></button>
            </span>
          ))}</div>
        </Row>
        <Row title="Watchlist" hint="Star any match card to add it here.">
          {prefs.watchlist.length ? (
            <ul className="flex flex-wrap gap-2">{prefs.watchlist.map((id) => (
              <li key={id} className="chip text-ink"><Link href={`/match/${id}`}>Match #{id}</Link>
                <button aria-label="Remove" onClick={() => update({ watchlist: prefs.watchlist.filter((x) => x !== id) })}><Trash2 size={12} /></button></li>
            ))}</ul>
          ) : <p className="text-sm text-muted">No saved matches yet.</p>}
        </Row>
        <Row id="notifications" title="Notifications" hint="Browser alert when a prediction for a watched match is published or updated (while the site is open).">
          <label className="flex items-center gap-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--neon))]" checked={prefs.notifications}
              onChange={async (e) => {
                const want = e.target.checked;
                if (want && typeof Notification !== "undefined" && Notification.permission !== "granted") {
                  const r = await Notification.requestPermission();
                  if (r !== "granted") return setMsg("Notifications were blocked by the browser.");
                }
                update({ notifications: want });
              }} />
            Notify me about watched matches
          </label>
        </Row>
        <Row title="Administrator" hint="Manually trigger a data refresh. The token is sent to the server only, never stored.">
          <div className="flex flex-wrap gap-2">
            <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Admin token" className={`${input} w-full sm:w-56`} autoComplete="off" />
            {["all", "fixtures", "live", "predict", "settle"].map((j) => (
              <button key={j} onClick={() => refresh(j)} disabled={!token} className="chip text-ink disabled:opacity-40"><RefreshCw size={12} />{j}</button>
            ))}
          </div>
          {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
        </Row>
      </div>
    </div>
  );
}
