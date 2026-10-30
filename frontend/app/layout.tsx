import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import "./globals.css";
import { Wordmark } from "@/components/Logo";
import { Nav, NotifyBell, SearchBox, ThemeToggle } from "@/components/client";
import { tryApi } from "@/lib/api";
import { THEME_BOOT } from "@/lib/prefs";
import type { Health } from "@/lib/types";

// Broadcast-scoreboard display face + a sober analytical body face.
const display = Barlow_Condensed({ subsets: ["latin"], variable: "--font-display", weight: ["500", "600", "700"] });
const sans = IBM_Plex_Sans({ subsets: ["latin"], variable: "--font-sans", weight: ["400", "500", "600"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: { default: "Football Predriction Boyz", template: "%s · Football Predriction Boyz" },
  applicationName: "Football Predriction Boyz",
  appleWebApp: { capable: true, title: "FP Boyz", statusBarStyle: "black" },
  icons: { apple: "/apple-icon.png" },
  description: "Smart Predictions. Better Football Insights. Statistical 1X2, BTTS and Over/Under probabilities for the Premier League, La Liga, Bundesliga, Ligue 1, Eliteserien and MLS.",
};

export const viewport: Viewport = { themeColor: "#0B1220", width: "device-width", initialScale: 1 };

async function StatusBanner() {
  const { data, error } = await tryApi<Health>("/api/health", 60);
  if (error || !data) {
    return (
      <div className="border-b border-bad/40 bg-bad/10 px-4 py-2 text-center text-xs text-bad">
        Prediction service unreachable — no data is shown until verified data is available again.
      </div>
    );
  }
  return (
    <>
      {data.demo && (
        <div className="border-b border-warn/40 bg-warn/10 px-4 py-2 text-center text-xs text-warn">
          <strong>DEMO MODE</strong> — fictional clubs and simulated results. Probabilities come from the real model, but no real football data is shown.
          Add <code className="font-mono">API_FOOTBALL_KEY</code> and <code className="font-mono">DATABASE_URL</code> to go live.
        </div>
      )}
      {data.warnings.filter((w) => !w.startsWith("Demo mode")).map((w) => (
        <div key={w} className="border-b border-warn/40 bg-warn/10 px-4 py-1.5 text-center text-xs text-warn">{w}</div>
      ))}
    </>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body className="min-h-screen font-sans antialiased">
        <Suspense fallback={null}>
          <StatusBanner />
        </Suspense>
        <header className="sticky top-0 z-30 border-b border-line/50 bg-bg/80 backdrop-blur-xl">
          <div className="mx-auto max-w-7xl px-4">
            <div className="flex items-center justify-between gap-3 py-3">
              <Link href="/" aria-label="Football Predriction Boyz home"><Wordmark /></Link>
              <div className="flex items-center gap-2">
                <div className="hidden md:block"><SearchBox /></div>
                <NotifyBell />
                <ThemeToggle />
              </div>
            </div>
            <Nav />
            <div className="pb-3 md:hidden"><SearchBox /></div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-10 pt-4 text-xs leading-relaxed text-muted">
          <div className="border-t border-line/50 pt-5">
            <p className="font-display font-semibold text-ink">Football Predriction Boyz <span className="font-sans font-normal text-muted">— Smart Predictions. Better Football Insights.</span></p>
            <p className="mt-2 max-w-3xl">
              Probabilities are statistical estimates from a Dixon-Coles goal model, not guarantees. A high probability is not the same as a
              profitable bet. Please gamble responsibly — in Norway, help is available from Hjelpelinjen (800 800 40).
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
