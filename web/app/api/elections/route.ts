import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SOURCE = "https://openamerica.io/elections/results.json";
const TIMEOUT_MS = 12000;
const MAX_BYTES = 4_000_000;

export async function GET(request: NextRequest) {
  const year = request.nextUrl.searchParams.get("year");
  const office = request.nextUrl.searchParams.get("office");
  if (!["2024", "2026"].includes(year ?? "") || !["House", "Senate"].includes(office ?? "")) {
    return NextResponse.json({ error: "Invalid election year or office" }, { status: 400 });
  }
  const url = new URL(SOURCE);
  url.searchParams.set("year", year!);
  url.searchParams.set("office", office!);
  try {
    const response = await fetch(url.toString(), {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    if (!response.ok) return NextResponse.json({ error: "Source unavailable" }, { status: 502 });
    const contentLength = Number(response.headers.get("content-length"));
    if (Number.isFinite(contentLength) && contentLength > MAX_BYTES) {
      return NextResponse.json({ error: "Source response too large" }, { status: 502 });
    }
    const body = await response.text();
    if (body.length > MAX_BYTES) return NextResponse.json({ error: "Source response too large" }, { status: 502 });
    const payload: unknown = JSON.parse(body);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Invalid response");
    const data = payload as Record<string, unknown>;
    if (data.api !== 1 || data.year !== Number(year) ||
        typeof data.office !== "string" || data.office.toLowerCase() !== office!.toLowerCase() ||
        !data.races || typeof data.races !== "object" || Array.isArray(data.races) ||
        !["live", "stale", "counting", "final"].every(field => typeof data[field] === "boolean")) {
      throw new Error("Unexpected feed schema");
    }
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Election source request failed" }, { status: 502 });
  }
}
