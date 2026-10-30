"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="glass mx-auto max-w-lg border-bad/40 p-6 text-center">
      <h1 className="font-display text-lg font-bold text-bad">Something went wrong</h1>
      <p className="mt-2 text-sm text-muted">{error.message}</p>
      <button onClick={reset} className="mt-4 rounded-lg bg-neon px-4 py-2 text-sm font-semibold text-bg">Try again</button>
    </div>
  );
}
