import { parseRollCall, ROLL_CALL_URL } from "../lib/newsroom-calls.ts";
try {
  const response = await fetch(ROLL_CALL_URL, { signal: AbortSignal.timeout(10000),
    headers: { Accept: "text/html", "User-Agent": "CivicPulse/1.1 (public election information viewer)" } });
  const html = await response.text();
  console.log("NEWSROOM_SOURCE_HTTP", response.status, "HTML_BYTES", html.length);
  if (response.ok) {
    const races = parseRollCall(html);
    console.log("NEWSROOM_PUBLISHED_TIME", races.updated);
    console.log("NEWSROOM_PARSED_CALL_COUNT", races.calls.length);
    console.log("NEWSROOM_SAMPLE", JSON.stringify(races.calls.slice(0,3)));
  }
} catch (error) {
  console.log("NEWSROOM_SOURCE_UNAVAILABLE", error instanceof Error ? error.message : String(error));
}
