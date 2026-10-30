import Link from "next/link";

export default function NotFound() {
  return (
    <div className="glass mx-auto max-w-lg p-6 text-center">
      <h1 className="font-display text-lg font-bold">Not found</h1>
      <p className="mt-2 text-sm text-muted">That match, league or page doesn&apos;t exist.</p>
      <Link href="/" className="mt-4 inline-block rounded-lg bg-neon px-4 py-2 text-sm font-semibold text-bg">Back to dashboard</Link>
    </div>
  );
}
