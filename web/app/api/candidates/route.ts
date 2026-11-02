import { inflateRawSync } from "node:zlib";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Candidate = { n: string; p: string };
type Roster = {
  authority: string;
  sourceUrl: string;
  kind: "ballot" | "filing";
  candidates: Candidate[];
};
type Index = Record<string, Roster>;

const FEC_URL = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip";
const NC_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv";
const REFRESH_MS = 6 * 60 * 60 * 1000;
const ZIP_LIMIT = 16_000_000;
const CSV_LIMIT = 15_000_000;
let cached: { expires: number; rosters: Index; sources: { authority: string; status: string; url: string }[] } | null = null;

function abbreviateParty(input: string): string {
  const party = input.trim().toUpperCase();
  return ({ DEM: "D", DEMOCRATIC: "D", REP: "R", REPUBLICAN: "R", LIB: "L", LIBERTARIAN: "L",
    GRE: "G", GREEN: "G", IND: "I", INDEPENDENT: "I", UNA: "U", NON: "—" } as Record<string, string>)[party]
    ?? (party.slice(0, 12) || "—");
}

async function download(url: string, maxBytes: number): Promise<Buffer> {
  const response = await fetch(url, {
    headers: { "User-Agent": "CivicPulseElectionViewer/1.0 (public-source-research)", Accept: "*/*" },
    signal: AbortSignal.timeout(18000),
    next: { revalidate: 21600 }
  });
  if (!response.ok) throw new Error("Source HTTP " + response.status);
  const size = Number(response.headers.get("content-length"));
  if (Number.isFinite(size) && size > maxBytes) throw new Error("Source exceeds size limit");
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > maxBytes) throw new Error("Source exceeds size limit");
  return bytes;
}

/** Read one small .txt entry from a ZIP's central directory (no external archive dependency). */
function readZipText(zip: Buffer): string {
  let end = -1;
  for (let i = zip.length - 22; i >= Math.max(0, zip.length - 65557); i--) {
    if (zip.readUInt32LE(i) === 0x06054b50) { end = i; break; }
  }
  if (end < 0) throw new Error("ZIP central directory not found");
  const count = zip.readUInt16LE(end + 10);
  const centralOffset = zip.readUInt32LE(end + 16);
  let at = centralOffset;
  for (let i = 0; i < count; i++) {
    if (at + 46 > zip.length || zip.readUInt32LE(at) !== 0x02014b50) throw new Error("Invalid ZIP entry");
    const method = zip.readUInt16LE(at + 10);
    const compressedSize = zip.readUInt32LE(at + 20);
    const uncompressedSize = zip.readUInt32LE(at + 24);
    const nameLength = zip.readUInt16LE(at + 28);
    const extraLength = zip.readUInt16LE(at + 30);
    const commentLength = zip.readUInt16LE(at + 32);
    const localOffset = zip.readUInt32LE(at + 42);
    const name = zip.subarray(at + 46, at + 46 + nameLength).toString("utf8");
    at += 46 + nameLength + extraLength + commentLength;
    if (!/(^|\/)cn(?:26)?\.txt$/i.test(name)) continue;
    if (uncompressedSize > CSV_LIMIT || compressedSize > ZIP_LIMIT) throw new Error("Candidate file exceeds size limit");
    if (localOffset + 30 > zip.length || zip.readUInt32LE(localOffset) !== 0x04034b50) throw new Error("Invalid ZIP entry header");
    const localNameLength = zip.readUInt16LE(localOffset + 26);
    const localExtraLength = zip.readUInt16LE(localOffset + 28);
    const start = localOffset + 30 + localNameLength + localExtraLength;
    if (start + compressedSize > zip.length) throw new Error("Truncated ZIP entry");
    const data = zip.subarray(start, start + compressedSize);
    const decoded = method === 8 ? inflateRawSync(data, { maxOutputLength: CSV_LIMIT })
      : method === 0 ? data : null;
    if (!decoded || decoded.length > CSV_LIMIT) throw new Error("Unsupported ZIP compression");
    return decoded.toString("utf8");
  }
  throw new Error("Candidate master text file missing from ZIP");
}

function parseFec(raw: string): Index {
  const rosters: Index = {};
  const known = new Map<string, Set<string>>();
  for (const line of raw.split(/\r?\n/)) {
    const f = line.split("|");
    if (f.length < 9 || f[3] !== "2026" || !["H", "S"].includes(f[5]) || f[8] !== "C") continue;
    const state = f[4].trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(state) || !f[1]?.trim()) continue;
    const district = f[6].trim().padStart(2, "0");
    if (f[5] === "H" && !/^\d{2}$/.test(district)) continue;
    const seat = f[5] === "H" ? state + "-" + district
      : (state === "OH" || state === "FL" ? state + "-SPECIAL" : state);
    const key = (f[5] === "H" ? "House:" : "Senate:") + seat;
    const id = f[0]?.trim();
    if (!id) continue;
    if (!rosters[key]) {
      rosters[key] = { authority: "Federal Election Commission", sourceUrl: FEC_URL,
        kind: "filing", candidates: [] };
      known.set(key, new Set());
    }
    if (known.get(key)!.has(id) || rosters[key].candidates.length >= 30) continue;
    known.get(key)!.add(id);
    rosters[key].candidates.push({ n: f[1].trim().slice(0, 160), p: abbreviateParty(f[2]) });
  }
  for (const roster of Object.values(rosters)) {
    roster.candidates.sort((a, b) => a.n.localeCompare(b.n));
  }
  return rosters;
}

/** Parse quoted CSV fields and newlines; only the five public ballot fields are retained. */
function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (c === '"') {
      if (quoted && source[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (c === "," && !quoted) {
      row.push(cell); cell = "";
    } else if ((c === "\n" || c === "\r") && !quoted) {
      if (c === "\r" && source[i + 1] === "\n") i++;
      row.push(cell); if (row.some(x => x.length)) rows.push(row);
      row = []; cell = "";
    } else { cell += c; }
  }
  if (quoted) throw new Error("Unterminated CSV field");
  if (row.length || cell.length) { row.push(cell); rows.push(row); }
  return rows;
}

function parseNorthCarolina(raw: string): Index {
  const rows = parseCsv(raw.replace(/^\uFEFF/, ""));
  const headers = rows.shift()?.map(x => x.trim().toLowerCase()) ?? [];
  const find = (name: string) => headers.indexOf(name);
  const dateCol = find("election_dt"), contestCol = find("contest_name");
  const nameCol = find("name_on_ballot"), partyCol = find("party_candidate");
  if ([dateCol, contestCol, nameCol, partyCol].some(i => i < 0)) throw new Error("NC CSV header changed");
  const rosters: Index = {};
  const seen = new Map<string, Set<string>>();
  for (const row of rows) {
    const date = row[dateCol]?.trim();
    if (!date || !/^(11\/0?3\/2026|11\/3\/2026|2026-11-03)$/.test(date)) continue;
    const contest = row[contestCol]?.trim().toUpperCase() ?? "";
    if (!/^(?:US|U\.S\.|UNITED STATES)\s+(?:HOUSE|SENATE)/.test(contest)) continue;
    const isHouse = /HOUSE/.test(contest);
    const district = contest.match(/DISTRICT\s*0*(\d{1,2})\b/);
    if (isHouse && !district) continue;
    const seat = isHouse ? "NC-" + district![1].padStart(2, "0") : "NC";
    const key = (isHouse ? "House:" : "Senate:") + seat;
    const name = row[nameCol]?.trim().slice(0, 160);
    if (!name) continue;
    const party = abbreviateParty(row[partyCol] ?? "");
    if (!rosters[key]) {
      rosters[key] = { authority: "North Carolina State Board of Elections", sourceUrl: NC_URL,
        kind: "ballot", candidates: [] };
      seen.set(key, new Set());
    }
    const id = (name + "|" + party).toUpperCase();
    if (seen.get(key)!.has(id)) continue;
    seen.get(key)!.add(id);
    rosters[key].candidates.push({ n: name, p: party });
  }
  if (!Object.keys(rosters).length) throw new Error("No NC federal general-election contests parsed");
  return rosters;
}

export async function GET() {
  if (cached && cached.expires > Date.now()) {
    return NextResponse.json(cached, { headers: { "Cache-Control": "public, s-maxage=300" } });
  }
  const output: { expires: number; rosters: Index; sources: { authority: string; status: string; url: string }[] } =
    { expires: Date.now() + REFRESH_MS, rosters: {}, sources: [] };
  const results = await Promise.allSettled([
    download(FEC_URL, ZIP_LIMIT).then(buffer => parseFec(readZipText(buffer))),
    download(NC_URL, CSV_LIMIT).then(buffer => parseNorthCarolina(buffer.toString("utf8")))
  ]);
  const names = ["Federal Election Commission", "North Carolina State Board of Elections"];
  const urls = [FEC_URL, NC_URL];
  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    if (result.status === "fulfilled") {
      Object.assign(output.rosters, result.value);
      output.sources.push({ authority: names[i], status: "available", url: urls[i] });
    } else {
      output.sources.push({ authority: names[i], status: "unavailable", url: urls[i] });
    }
  }
  // Avoid caching complete source outages for six hours; retry after one minute.
  if (results.every(result => result.status === "rejected")) output.expires = Date.now() + 60_000;
  cached = output;
  return NextResponse.json(output, { headers: { "Cache-Control": "public, s-maxage=300" } });
}
