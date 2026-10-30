/**
 * Football Predriction Boyz mark: a football whose right half resolves into an
 * analytics chart — rising bars joined by a neural "prediction" line.
 */
export function LogoMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label="Football Predriction Boyz logo">
      <defs>
        <linearGradient id="fpb-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgb(var(--neon))" />
          <stop offset="1" stopColor="rgb(var(--sky))" />
        </linearGradient>
        <clipPath id="fpb-left"><rect x="0" y="0" width="32" height="64" /></clipPath>
        <clipPath id="fpb-ball"><circle cx="32" cy="32" r="27" /></clipPath>
      </defs>
      <circle cx="32" cy="32" r="29" fill="rgb(var(--bg))" stroke="url(#fpb-g)" strokeWidth="3" />
      {/* left half: classic football panels */}
      <g clipPath="url(#fpb-left)">
        <g clipPath="url(#fpb-ball)" fill="none" stroke="rgb(var(--ink))" strokeWidth="2.2" strokeLinejoin="round">
          <polygon points="32,21 41,27.5 37.5,38 26.5,38 23,27.5" fill="rgb(var(--ink))" />
          <path d="M23 27.5 L12 24 M26.5 38 L20 47 M32 21 L32 9 M12 24 L8 36 M20 47 L30 56" />
        </g>
      </g>
      {/* right half: analytics bars + prediction line */}
      <g clipPath="url(#fpb-ball)">
        <rect x="35" y="38" width="5" height="14" rx="1.5" fill="rgb(var(--neon))" opacity="0.55" />
        <rect x="42" y="31" width="5" height="21" rx="1.5" fill="rgb(var(--neon))" opacity="0.75" />
        <rect x="49" y="23" width="5" height="29" rx="1.5" fill="rgb(var(--neon))" />
        <polyline points="35,30 44.5,22 51.5,14" fill="none" stroke="rgb(var(--sky))" strokeWidth="2.2" strokeLinecap="round" />
        <circle cx="35" cy="30" r="2.4" fill="rgb(var(--sky))" />
        <circle cx="44.5" cy="22" r="2.4" fill="rgb(var(--sky))" />
        <circle cx="51.5" cy="14" r="2.8" fill="rgb(var(--neon))" />
      </g>
      <line x1="32" y1="5" x2="32" y2="59" stroke="url(#fpb-g)" strokeWidth="1.2" strokeDasharray="2 2.5" />
    </svg>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <LogoMark size={compact ? 32 : 40} />
      <div className="leading-tight">
        <div className="font-display text-[15px] font-bold tracking-tight sm:text-base">
          Football <span className="text-neon">Predriction</span> Boyz
        </div>
        {!compact && (
          <div className="hidden text-[11px] text-muted sm:block">Smart Predictions. Better Football Insights.</div>
        )}
      </div>
    </div>
  );
}
