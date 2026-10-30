"use client";
import { useCallback, useEffect, useState } from "react";

export type Prefs = {
  tz: string;
  theme: "dark" | "light";
  oddsFormat: "decimal";
  favLeagues: string[];
  favTeams: string[];
  watchlist: number[];
  notifications: boolean;
};

export const DEFAULT_PREFS: Prefs = {
  tz: "Europe/Oslo", theme: "dark", oddsFormat: "decimal", favLeagues: [], favTeams: [], watchlist: [], notifications: false,
};

const KEY = "fpb_prefs";

export function readPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : DEFAULT_PREFS;
  } catch {
    return DEFAULT_PREFS;
  }
}

export function writePrefs(p: Prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable (private mode) — preferences last for this page only */
  }
  document.cookie = `fpb_tz=${encodeURIComponent(p.tz)}; path=/; max-age=31536000; samesite=lax`;
  document.documentElement.dataset.theme = p.theme;
  window.dispatchEvent(new CustomEvent("fpb-prefs", { detail: p }));
}

export function usePrefs(): [Prefs, (update: Partial<Prefs>) => void] {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  useEffect(() => {
    setPrefs(readPrefs());
    const on = (e: Event) => setPrefs((e as CustomEvent<Prefs>).detail);
    window.addEventListener("fpb-prefs", on);
    return () => window.removeEventListener("fpb-prefs", on);
  }, []);
  const update = useCallback((u: Partial<Prefs>) => {
    const next = { ...readPrefs(), ...u };
    writePrefs(next);
    setPrefs(next);
  }, []);
  return [prefs, update];
}

/** Inline script for <head>: applies the saved theme before first paint (no flash). */
export const THEME_BOOT = `try{var p=JSON.parse(localStorage.getItem('${KEY}')||'{}');document.documentElement.dataset.theme=p.theme||'dark'}catch(e){document.documentElement.dataset.theme='dark'}`;
