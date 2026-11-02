/** Source-derived election status only: no forecasts or inferred winners. */
export type BoardCandidate = { n?: string; p?: string; v?: number | null; pct?: number | null };
export type BoardRace = {
  cands?: BoardCandidate[];
  total?: number | null;
  pct_in?: number | null;
  called?: boolean;
  winner?: string | null;
  leader?: string | null;
};

export function safeVote(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

export function partyCode(value: unknown): string {
  const party = typeof value === "string" ? value.trim().toUpperCase() : "";
  const aliases: Record<string, string> = {
    D: "D", DEM: "D", DEMOCRAT: "D", DEMOCRATIC: "D",
    R: "R", REP: "R", REPUBLICAN: "R",
    I: "I", IND: "I", INDEPENDENT: "I",
    L: "L", LIB: "L", LIBERTARIAN: "L",
    G: "G", GRE: "G", GREEN: "G",
    U: "U", UNAFFILIATED: "U"
  };
  return aliases[party] ?? (party || "—").slice(0, 12);
}

export function partyLabel(value: unknown): string {
  const code = partyCode(value);
  const labels: Record<string, string> = {
    D: "Democratic", R: "Republican", I: "Independent",
    L: "Libertarian", G: "Green", U: "Unaffiliated", "—": "Party not listed"
  };
  return labels[code] ?? code;
}

export type RaceInsight = {
  leader: BoardCandidate | null;
  runnerUp: BoardCandidate | null;
  voteMargin: number | null;
  marginPct: number | null;
  close: boolean;
  sourceCalledWinner: string | null;
};

/** Only calculate margins from published candidate votes and a compatible race total. */
export function raceInsight(race: BoardRace | null | undefined): RaceInsight {
  const candidates = (Array.isArray(race?.cands) ? race.cands : []).filter(
    c => c && typeof c.n === "string" && c.n.trim().length > 0 && safeVote(c.v)
  );
  const sorted = candidates.slice().sort((a, b) => (b.v as number) - (a.v as number));
  const hasVotes = sorted.some(c => (c.v as number) > 0) || (safeVote(race?.total) && (race?.total ?? 0) > 0);
  const winnerName = typeof race?.winner === "string" ? race.winner.trim() : "";
  // A source call requires an explicit 'called' flag and positive published votes.
  const sourceCalledWinner = hasVotes && race?.called === true && winnerName ? winnerName : null;
  if (!hasVotes || sorted.length < 1 || (sorted[0].v as number) === 0) {
    return {leader: null, runnerUp: null, voteMargin: null, marginPct: null, close: false, sourceCalledWinner};
  }
  const first = sorted[0], second = sorted[1];
  if (!second || (first.v as number) === (second.v as number)) {
    return {leader: null, runnerUp: second ?? null, voteMargin: null, marginPct: null, close: false, sourceCalledWinner};
  }
  const gap = (first.v as number) - (second.v as number);
  const total = race?.total;
  const marginPct = safeVote(total) && total > 0 && total >= (first.v as number) + (second.v as number)
    ? gap / total * 100 : null;
  return {
    leader: first, runnerUp: second, voteMargin: gap, marginPct,
    close: marginPct !== null && marginPct <= 2 && !sourceCalledWinner,
    sourceCalledWinner
  };
}

/** Resolve the party of an explicit publisher-called winner only when its name matches a reported candidate. */
export function sourceCalledParty(race: BoardRace | null | undefined): string | null {
  const winner = raceInsight(race).sourceCalledWinner?.toLocaleLowerCase("en-US");
  if (!winner || !Array.isArray(race?.cands)) return null;
  const matched = race.cands.find(c =>
    typeof c?.n === "string" && c.n.trim().toLocaleLowerCase("en-US") === winner
  );
  return matched ? partyCode(matched.p) : null;
}
