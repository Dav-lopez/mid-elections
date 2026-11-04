import { NextResponse } from "next/server";
import { parseElectionNightPage, type ElectionNightSnapshot } from "../../../lib/election-night";
import { parseRollCall, ROLL_CALL_URL } from "../../../lib/newsroom-calls";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const INDEPENDENT_SOURCE = "https://www.poliwave.com/us/live/midterms-2026";
const TTL_MS = 65_000;
const REQUEST_MS = 9_000;

type Call = {
  state: string;
  office: "House" | "Senate" | "Governor";
  district?: string;
  winner: string;
  party: string;
  sourceUrl: string;
  sourceLabel?: string;
};
type NightPayload = {
  source: string;
  sourceUrl: string;
  sourceUpdated: string;
  fetchedAt: string;
  stale: boolean;
  sourceUnavailable?: boolean;
  headline: string;
  offices: ElectionNightSnapshot["offices"] | null;
  calls: Call[];
};
let cache: {expires: number; value: NightPayload} | null = null;
let inflight: Promise<NightPayload> | null = null;

async function loadHtml(url: string): Promise<string> {
  const response = await fetch(url, {
    signal: AbortSignal.timeout(REQUEST_MS),
    headers: { Accept: "text/html", "User-Agent": "CivicPulse/1.1 (public election information viewer)" },
    next: { revalidate: 60 }
  });
  if (!response.ok) throw new Error("Results source HTTP " + response.status);
  const length = Number(response.headers.get("content-length"));
  if (Number.isFinite(length) && length > 2_000_000) throw new Error("HTML response too large");
  const html = await response.text();
  if (html.length > 2_000_000) throw new Error("HTML response too large");
  return html;
}

async function fromIndependentScoreboard(): Promise<NightPayload> {
  const html = await loadHtml(INDEPENDENT_SOURCE);
  return parseElectionNightPage(html, new Date().toISOString());
}

async function fromNewsroom(): Promise<NightPayload> {
  const html = await loadHtml(ROLL_CALL_URL);
  const parsed = parseRollCall(html);
  return {
    source: "CQ Roll Call (AP-attributed race calls)",
    sourceUrl: ROLL_CALL_URL,
    sourceUpdated: parsed.updated,
    fetchedAt: new Date().toISOString(),
    stale: true,
    sourceUnavailable: false,
    headline: "Named reported winners, not live nationwide seat totals or official certification",
    offices: null,
    calls: parsed.calls
  };
}

// These are explicitly named calls checked against dated public reporting.
// Keep the URLs with each assertion. The national balance cannot be inferred
// from this selected list, nor should fetching this static list imply freshness.
const DATED_REPORTS: Call[] = [
  {state:"Georgia", office:"Senate", winner:"Jon Ossoff", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"New Hampshire", office:"Senate", winner:"Chris Pappas", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"North Carolina", office:"Senate", winner:"Roy Cooper", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"Florida", office:"Senate", winner:"Ashley Moody", party:"R", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"Florida", office:"House", district:"25", winner:"Jared Moskowitz", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"Florida", office:"House", district:"14", winner:"Kathy Castor", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"Florida", office:"House", district:"16", winner:"Sydney Gruters", party:"R", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"North Carolina", office:"House", district:"11", winner:"Jamie Ager", party:"D", sourceLabel:"CQ Roll Call reporting AP call", sourceUrl:ROLL_CALL_URL},
  {state:"Ohio", office:"Senate", winner:"Sherrod Brown", party:"D", sourceLabel:"Associated Press article", sourceUrl:"https://apnews.com/article/9e7ae9e1715c0e8203614aea6f71666d"},
  {state:"Texas", office:"Senate", winner:"James Talarico", party:"D", sourceLabel:"Associated Press article", sourceUrl:"https://apnews.com/article/f126e12e05b579a327b98481c0ae2226"},
  {state:"South Carolina", office:"Senate", winner:"Annie Andrews", party:"D", sourceLabel:"Associated Press article", sourceUrl:"https://apnews.com/article/f126e12e05b579a327b98481c0ae2226"},
  {state:"Ohio", office:"Governor", winner:"Amy Acton", party:"D", sourceLabel:"Associated Press article", sourceUrl:"https://apnews.com/article/f126e12e05b579a327b98481c0ae2226"},
  {state:"Georgia", office:"Governor", winner:"Keisha Lance Bottoms", party:"D", sourceLabel:"Guardian election-night reporting", sourceUrl:"https://www.theguardian.com/us-news/live/2026/nov/03/midterm-election-results-live-updates"},
  {state:"Florida", office:"Governor", winner:"Byron Donalds", party:"R", sourceLabel:"Guardian election-night reporting", sourceUrl:"https://www.theguardian.com/us-news/live/2026/nov/03/midterm-election-results-live-updates"}
];

function datedFallback(): NightPayload {
  return {
    source: "Dated CQ Roll Call / AP / Guardian reports",
    sourceUrl: ROLL_CALL_URL,
    sourceUpdated: "Reported on November 3, 2026; not automatically synchronized",
    fetchedAt: new Date().toISOString(),
    stale: true,
    sourceUnavailable: true,
    headline: "Verified published calls only; national seat balance unavailable. Not an AP data subscription.",
    offices: null,
    calls: DATED_REPORTS
  };
}

async function getCurrent(): Promise<NightPayload> {
  // Each independent source is allowed to fail without hiding the other sources.
  try {
    return await fromIndependentScoreboard();
  } catch {
    try {
      return await fromNewsroom();
    } catch {
      return datedFallback();
    }
  }
}

export async function GET() {
  const header = { "Cache-Control": "public, s-maxage=10, stale-while-revalidate=50" };
  if (cache && cache.expires > Date.now()) return NextResponse.json(cache.value, { headers: header });
  try {
    inflight ??= getCurrent();
    const value = await inflight;
    cache = { expires: Date.now() + (value.sourceUnavailable ? 90_000 : TTL_MS), value };
    return NextResponse.json(value, { headers: header });
  } catch {
    // Protect users from displaying fabricated zeroes or promises of current results.
    const last = cache?.value;
    if (last) return NextResponse.json({...last, stale:true, sourceUnavailable:true},
      {headers:{"Cache-Control":"no-store"}});
    return NextResponse.json(datedFallback(), { headers: {"Cache-Control":"public, s-maxage=60"} });
  } finally {
    inflight = null;
  }
}
