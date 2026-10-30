import { NextRequest, NextResponse } from "next/server";

/** Browser -> Next.js -> backend. Keeps BACKEND_URL server-side; only GET + admin refresh are allowed. */
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const ALLOWED_GET = /^(health|leagues|fixtures|predictions|analytics|history|search)(\/|$)/;

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (!ALLOWED_GET.test(path)) return NextResponse.json({ error: "not allowed" }, { status: 404 });
  const r = await fetch(`${BACKEND}/api/${path}${req.nextUrl.search}`, { cache: "no-store" }).catch(() => null);
  if (!r) return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  return new NextResponse(await r.text(), { status: r.status, headers: { "content-type": "application/json" } });
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (path !== "admin/refresh") return NextResponse.json({ error: "not allowed" }, { status: 404 });
  const token = req.headers.get("x-admin-token") ?? "";
  const r = await fetch(`${BACKEND}/api/admin/refresh${req.nextUrl.search}`, {
    method: "POST", headers: { "x-admin-token": token }, cache: "no-store",
  }).catch(() => null);
  if (!r) return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  return new NextResponse(await r.text(), { status: r.status, headers: { "content-type": "application/json" } });
}
