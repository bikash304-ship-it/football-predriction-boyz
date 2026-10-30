"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Bell, Moon, Search, Star, Sun } from "lucide-react";
import { usePrefs } from "@/lib/prefs";

export const NAV = [
  { href: "/", label: "Home" },
  { href: "/today", label: "Today" },
  { href: "/tomorrow", label: "Tomorrow" },
  { href: "/leagues", label: "Leagues" },
  { href: "/predictions", label: "Predictions" },
  { href: "/analytics", label: "Analytics" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const path = usePathname();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <nav aria-label="Main" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex gap-1">
        {NAV.map((n) => (
          <li key={n.href}>
            <Link
              href={n.href}
              aria-current={isActive(n.href) ? "page" : undefined}
              className={`relative block whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive(n.href) ? "text-ink" : "text-muted hover:bg-card2/60 hover:text-ink"
              }`}
            >
              {n.label}
              {isActive(n.href) && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-neon shadow-glow" />}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function ThemeToggle() {
  const [prefs, update] = usePrefs();
  const dark = prefs.theme === "dark";
  return (
    <button
      onClick={() => update({ theme: dark ? "light" : "dark" })}
      className="grid h-9 w-9 place-items-center rounded-lg border border-line/70 bg-card/70 text-muted hover:text-ink"
      aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

export function WatchButton({ id }: { id: number }) {
  const [prefs, update] = usePrefs();
  const on = prefs.watchlist.includes(id);
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        update({ watchlist: on ? prefs.watchlist.filter((x) => x !== id) : [...prefs.watchlist, id] });
      }}
      aria-pressed={on}
      aria-label={on ? "Remove from watchlist" : "Add to watchlist"}
      className={`grid h-6 w-6 place-items-center rounded-md transition ${on ? "text-warn" : "text-muted/60 hover:text-ink"}`}
    >
      <Star size={14} fill={on ? "currentColor" : "none"} />
    </button>
  );
}

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        if (q.trim().length >= 2) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
      }}
      className="relative"
    >
      <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search clubs & matches"
        aria-label="Search clubs and matches"
        className="h-9 w-full rounded-lg border border-line/70 bg-card/70 pl-9 pr-3 text-sm placeholder:text-muted/70 focus:border-neon/60 focus:outline-none sm:w-60"
      />
    </form>
  );
}

/** Re-renders server data on an interval (live scores ~45s, schedules ~5 min). Pauses in background tabs. */
export function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, seconds * 1000);
    return () => clearInterval(t);
  }, [router, seconds]);
  return null;
}

/** Fires a browser notification when a watched/favourite match gets a new or updated prediction. */
export function PredictionNotifier({ stamps }: { stamps: { id: number; label: string; updated: string }[] }) {
  const [prefs] = usePrefs();
  const seen = useRef<Record<number, string>>({});
  useEffect(() => {
    if (!prefs.notifications || typeof Notification === "undefined" || Notification.permission !== "granted") return;
    let store: Record<number, string> = {};
    try { store = JSON.parse(localStorage.getItem("fpb_seen") || "{}"); } catch {}
    for (const s of stamps) {
      if (!prefs.watchlist.includes(s.id)) continue;
      if (store[s.id] && store[s.id] !== s.updated && seen.current[s.id] !== s.updated) {
        new Notification("Prediction updated", { body: s.label, icon: "/logo.svg" });
      }
      store[s.id] = s.updated;
      seen.current[s.id] = s.updated;
    }
    try { localStorage.setItem("fpb_seen", JSON.stringify(store)); } catch {}
  }, [stamps, prefs]);
  return null;
}

export function NotifyBell() {
  const [prefs] = usePrefs();
  return (
    <Link href="/settings#notifications" aria-label="Notification settings"
      className={`grid h-9 w-9 place-items-center rounded-lg border border-line/70 bg-card/70 ${prefs.notifications ? "text-neon" : "text-muted hover:text-ink"}`}>
      <Bell size={16} />
    </Link>
  );
}

/** League filter chips that write ?league= to the URL (server re-renders the list). */
export function LeagueFilter({ leagues }: { leagues: { slug: string; name: string; flag: string }[] }) {
  const router = useRouter();
  const sp = useSearchParams();
  const path = usePathname();
  const cur = sp.get("league");
  const go = (slug: string | null) => {
    const p = new URLSearchParams(sp.toString());
    if (slug) p.set("league", slug); else p.delete("league");
    router.push(`${path}?${p.toString()}`, { scroll: false });
  };
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-1">
      <button onClick={() => go(null)} className={`chip whitespace-nowrap ${!cur ? "chip-on" : ""}`}>All leagues</button>
      {leagues.map((l) => (
        <button key={l.slug} onClick={() => go(l.slug)} className={`chip whitespace-nowrap ${cur === l.slug ? "chip-on" : ""}`}>
          <span aria-hidden>{l.flag}</span>{l.name}
        </button>
      ))}
    </div>
  );
}
