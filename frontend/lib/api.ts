import "server-only";
import { cookies } from "next/headers";

/** Server-side only: the backend URL (and any keys) never reach the browser. */
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, revalidate = 30): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND}${path}`, { next: { revalidate }, signal: AbortSignal.timeout(12000) });
  } catch {
    throw new ApiError(503, "The prediction service is unreachable. Showing nothing rather than unverified data.");
  }
  if (!res.ok) throw new ApiError(res.status, `${path} → HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

/** Same call, but returns an error object instead of throwing (for partial page rendering). */
export async function tryApi<T>(path: string, revalidate = 30): Promise<{ data: T | null; error: string | null }> {
  try {
    return { data: await api<T>(path, revalidate), error: null };
  } catch (e) {
    return { data: null, error: e instanceof Error ? e.message : "Unknown error" };
  }
}

export async function userTz(): Promise<string> {
  const c = await cookies();
  return c.get("fpb_tz")?.value || process.env.DEFAULT_TIMEZONE || "Europe/Oslo";
}
