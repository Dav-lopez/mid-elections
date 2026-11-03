import { load } from "cheerio";

export type OfficialPageCandidate = { n:string; p:string; v:number|null; pct:number|null };
export type OfficialPageContest = {
  seat: string;
  cands: OfficialPageCandidate[];
  total: number|null;
  pct_in: number|null;
  sourceUrl: string;
  updatedLabel: string|null;
  called: false;
  winner: "";
};

export const MARYLAND_OFFICIAL_RESULTS_INDEX = "https://elections.maryland.gov/elections/2026/General_results/index.html";
const BASE = "https://elections.maryland.gov/elections/2026/General_results/";
export const marylandHouseUrl = (district:number) => BASE+"gen_results_2026_4_"+district+".html";

const parties:Record<string,string> = {
  DEMOCRATIC:"D", REPUBLICAN:"R", GREEN:"G", LIBERTARIAN:"L",
  UNAFFILIATED:"I", INDEPENDENT:"I", OTHER:"O",
};
const clean = (s:string) => s.replace(/\s+/g," ").trim();
const number = (s:string):number|null => {
  const value=clean(s).replace(/,/g,"");
  if (!/^\d+$/.test(value)) return null;
  const parsed=Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
};
const percentage = (s:string):number|null => {
  const value=clean(s).replace(/%$/, "");
  if (!/^\d+(?:\.\d+)?$/.test(value)) return null;
  const result=Number(value);
  return Number.isFinite(result) && result >= 0 && result <= 100 ? result:null;
};

/** Parse a verified, fixed Maryland congressional results page.
 * Do not interpret the site's generic "winner" legend as a race call.
 * The official state posts "NR" before voting totals are released.
 */
export function parseMarylandHouse(html:string,district:number):OfficialPageContest {
  if(!Number.isInteger(district)||district<1||district>8)throw new Error("District outside Maryland House scope");
  if(html.length>1_000_000)throw new Error("Page too large");
  const $=load(html);
  const visible=clean($("body").text());
  if(!/Unofficial 2026 Gubernatorial General Election Results/i.test(visible) ||
     !/Representative in Congress/i.test(visible) ||
     !new RegExp("District\\s+"+district+"\\b","i").test(visible)){
    throw new Error("Maryland election page identity mismatch");
  }
  const rows=$("table tr").toArray().map(node=>
    $(node).children("th,td").toArray().map(cell=>clean($(cell).text()))
  );
  const header=rows.findIndex(row=>row.length>=7 &&
    row[0]?.toLowerCase()==="name" &&
    row[1]?.toLowerCase()==="party" &&
    row.some(field=>field.toLowerCase()==="total") &&
    row.some(field=>field.toLowerCase()==="percentage")
  );
  if(header<0)throw new Error("Maryland published results table not found");
  const tableHeader=rows[header].map(v=>v.toLowerCase());
  const votesCol=tableHeader.indexOf("total");
  const pctCol=tableHeader.indexOf("percentage");
  const candidates:OfficialPageCandidate[]=[];
  const seen=new Set<string>();
  let publishedTotal:number|null=null;
  for(let index=header+1;index<rows.length;index++){
    const row=rows[index];
    if(row.length<7)break;
    const name=row[0]?.slice(0,150)??"";
    const party=parties[(row[1]??"").toUpperCase()];
    const votes=number(row[votesCol]??"");
    if(/^totals?$/i.test(name)){
      publishedTotal=votes;
      break;
    }
    if(!name || !party || /^other write-ins/i.test(name) ||
      /\b(?:password|sign in)\b/i.test(name))continue;
    const identifier=(name+"|"+party).toUpperCase();
    if(seen.has(identifier))continue;
    seen.add(identifier);
    candidates.push({n:name,p:party,v:votes,pct:percentage(row[pctCol]??"")});
    if(candidates.length>=24)break;
  }
  if(!candidates.length)throw new Error("Maryland results table contains no identifiable candidates");
  const reported=candidates.some(candidate=>candidate.v!==null && candidate.v>0);
  const officialTotal=publishedTotal!==null && publishedTotal>0?publishedTotal:null;
  // Never manufacture a race-wide total by summing a possibly partial candidate list.
  const total=reported?officialTotal:null;
  const precincts=visible.match(/(\d+)\s+of\s+(\d+)\s+election day precincts reported/i);
  const seenPrecinct=precincts?Number(precincts[1]):null;
  const allPrecinct=precincts?Number(precincts[2]):null;
  const pct_in=reported && seenPrecinct!==null && allPrecinct!==null && allPrecinct>0 &&
    seenPrecinct<=allPrecinct ? Math.round(seenPrecinct/allPrecinct*10000)/100:null;
  const timestamp=visible.match(/Last refreshed:\s*(\d{1,2}\/\d{1,2}\/2026\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)/i);
  return {
    seat:"MD-"+String(district).padStart(2,"0"),cands:candidates,total,pct_in,
    sourceUrl:marylandHouseUrl(district),
    updatedLabel:timestamp?timestamp[1]+" Eastern":null,
    called:false,winner:""
  };
}
