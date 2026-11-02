/** Manually reviewed official general-election candidate rosters.
 * Distinct from election-night results: never infer votes from these entries.
 * Review against each election authority when new revisions are published.
 */
export type RosterCandidate = {n:string;p:string};
export type OfficialRoster = {authority:string;verifiedAsOf:string;sourceUrl:string;candidates:RosterCandidate[]};
const iowaSource="https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf";
const ohioSource="https://www.boe.ohio.gov/abmt/oh75/20261103/X0029__1_0029_PERRY.html";
const iowa=(candidates:RosterCandidate[]):OfficialRoster=>({authority:"Iowa Secretary of State",verifiedAsOf:"2026-08-19",sourceUrl:iowaSource,candidates});
export const officialRosters:Record<string,OfficialRoster>={
  "Senate:IA":iowa([{n:"Ashley Hinson",p:"R"},{n:"Josh Turek",p:"D"},{n:"Thomas Laehn",p:"L"}]),
  "House:IA-01":iowa([{n:"Mariannette Miller-Meeks",p:"R"},{n:"Christina Bohannan",p:"D"},{n:"Michael Bridgford",p:"I"}]),
  "House:IA-02":iowa([{n:"Joe Mitchell",p:"R"},{n:"Lindsay James",p:"D"},{n:"Rick Stewart",p:"L"},{n:"Dave Bushaw",p:"I"}]),
  "House:IA-03":iowa([{n:"Zach Nunn",p:"R"},{n:"Sarah Trone Garriott",p:"D"}]),
  "House:IA-04":iowa([{n:"Chris McGowan",p:"R"},{n:"Dave Dawson",p:"D"}]),
  "Senate:OH-SPECIAL":{
    authority:"Ohio Board of Elections — official November 3 sample ballot",
    verifiedAsOf:"2026-11-02",
    sourceUrl:ohioSource,
    candidates:[{n:"Sherrod Brown",p:"D"},{n:"Jon Husted",p:"R"},{n:"Greg Levy",p:"I"},{n:"William B. Redpath",p:"L"}]
  }
};
