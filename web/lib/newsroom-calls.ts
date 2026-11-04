import { load } from "cheerio";

/** Newsroom list of AP-attributed *race calls*, not an official AP data feed. */
export type NewsroomCall = {
  state: string;
  office: "Senate" | "Governor" | "House";
  district?: string;
  winner: string;
  party: "D" | "R";
  sourceLabel: string;
  sourceUrl: string;
};
export type NewsroomCalls = { calls: NewsroomCall[]; updated: string; sourceUrl: string };

export const ROLL_CALL_URL = "https://rollcall.com/2026/11/03/key-midterm-election-results/";

const STATES = [
  "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
  "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
  "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
  "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
  "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
  "New Hampshire", "New Jersey", "New Mexico", "New York",
  "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
  "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
  "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
  "West Virginia", "Wisconsin", "Wyoming"
];
const STATE_PATTERN = STATES.map(name => name.replace(/\s+/g, "\\s+")).join("|");
const SENATE_GOVERNOR = new RegExp("^(" + STATE_PATTERN + ")\\s+(Senate|Governor)(?:\\s+\\([^)]*\\))?:\\s+(.+)$", "i");
const HOUSE = new RegExp("^(" + STATE_PATTERN + ")[’']s?\\s+(\\d{1,2})(?:st|nd|rd|th)\\s+District(?:\\s+\\([^)]*\\))?:\\s+(.+)$", "i");

function strip(s: string) { return s.replace(/\s+/g, " ").trim(); }

function extractWinner(prefix: string): string | null {
  // Named winner appears before 'defeats'. Limit extraction to personal names;
  // never infer a winner from a "leading", "ahead", or "projected" sentence.
  const subject = prefix.split(",")[0].trim();
  const match = subject.match(/([A-Z][\p{L}'’-]+(?:\s+[A-Z][\p{L}'’-]+){1,3})$/u);
  if (!match) return null;
  const value = strip(match[1]);
  return value.length >= 5 && value.length <= 100 ? value : null;
}

export function parseRollCall(html: string): NewsroomCalls {
  if (html.length > 2_000_000) throw new Error("Newsroom article too large");
  const $ = load(html);
  const body = strip($("body").text());
  if (!/Key midterm election results/i.test(body) ||
      !/tracking the results.*?called by The Associated Press/i.test(body)) {
    throw new Error("Newsroom article identity or AP attribution not verified");
  }
  const updated = body.match(/Last updated at (\d{1,2}:\d{2}\s*[ap]\.m\.\s*Eastern time)/i)?.[1] ?? "Time not published";
  const nodes = $("p, li").toArray();
  const calls: NewsroomCall[] = [];
  const seen = new Set<string>();
  for (const node of nodes) {
    const text = strip($(node).text());
    if (!text || text.length > 700) continue;
    // The result must explicitly say the named candidate "defeats" another
    // and carry the source's '[Democratic hold]' or '[Republican flip]' designation.
    const label = text.match(/\[(Democratic|Republican)\s+(hold|flip|gain)\]$/i);
    if (!label || !/\bdefeats\b/i.test(text)) continue;
    const party = label[1].toLowerCase() === "democratic" ? "D" : "R";
    const withoutLabel = strip(text.slice(0, label.index));
    const matchSg = withoutLabel.match(SENATE_GOVERNOR);
    const matchHouse = withoutLabel.match(HOUSE);
    if (!matchSg && !matchHouse) continue;
    const state = (matchSg?.[1] ?? matchHouse?.[1])!;
    const office = matchSg ? matchSg[2] as "Senate" | "Governor" : "House" as const;
    const district = matchHouse?.[2];
    const sentence = (matchSg?.[3] ?? matchHouse?.[3])!;
    const start = sentence.split(/\s+defeats\s+/i)[0];
    const winner = extractWinner(start);
    if (!winner) continue;
    const key = [state,office,district??""].join(":");
    if (seen.has(key)) continue;
    seen.add(key);
    calls.push({
      state, office, ...(district ? { district: district.padStart(2,"0") } : {}),
      winner, party, sourceLabel: "CQ Roll Call (AP-attributed call)",
      sourceUrl: ROLL_CALL_URL
    });
  }
  if (!calls.length) throw new Error("No explicit race calls parsed; article structure may have changed");
  return {calls, updated:"November 3, 2026 · "+updated, sourceUrl:ROLL_CALL_URL};
}
