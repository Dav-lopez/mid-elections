import {load} from "cheerio";

export type SeatTotals={
 office:"House"|"Senate"|"Governor";
 seats:number;
 called:number;
 dem:number;
 rep:number;
 independent?:number;
 demLeading:number;
 repLeading:number;
};
export type VerifiedCall={
 office:"Senate"|"Governor"|"House";
 state:string;
 winner:string;
 party:"D"|"R"|"I";
 sourceUrl:string;
};
export type ElectionNightSnapshot={
 source:"Poliwave";
 sourceUrl:string;
 sourceUpdated:string;
 fetchedAt:string;
 stale:boolean;
 headline:string;
 offices:Record<"House"|"Senate"|"Governor",SeatTotals>;
 calls:VerifiedCall[];
};
const SOURCE="https://www.poliwave.com/us/live/midterms-2026";
const integer=(s:string|undefined):number=>s?Number(s):0;
const normalize=(s:string)=>s.replace(/\s+/g," ").trim();

function readScoreboard(body:string,office:"House"|"Senate"|"Governor"):SeatTotals {
  // This is the *called/not-on-ballot* balance, never the website's forecast.
  const common=office==="House"
    ? /(?:^|\s)House\s+435 seats up\s*[·•]\s*(\d+) called\s+Democrats\s+(\d+)(?:\+(\d+) leading)?\s+Republicans\s+(\d+)(?:\+(\d+) leading)?/i
    : office==="Senate"
    ? /(?:^|\s)Senate\s+35 of 100 seats up\s*[·•]\s*(\d+) called\s+Democrats\s+(\d+)(?:\+(\d+) leading)?\s+Republicans\s+(\d+)(?:\+(\d+) leading)?\s+Ind\.\s+(\d+)/i
    : /(?:^|\s)Governors\s+36 of 50 races up\s*[·•]\s*(\d+) called\s+Democrats\s+(\d+)(?:\+(\d+) leading)?\s+Republicans\s+(\d+)(?:\+(\d+) leading)?/i;
  const match=body.match(common);
  if(!match)throw new Error("Election-night "+office+" balance format changed");
  const seats=office==="House"?435:office==="Senate"?100:50;
  const called=integer(match[1]),dem=integer(match[2]),demLeading=integer(match[3]);
  const rep=integer(match[4]),repLeading=integer(match[5]);
  const independent=office==="Senate"?integer(match[6]):undefined;
  if([called,dem,rep,demLeading,repLeading,independent??0].some(n=>!Number.isInteger(n)||n<0||n>seats) ||
     dem+rep+(independent??0)>seats ||
     called>(office==="Senate"?35:office==="Governor"?36:435)){
    throw new Error("Election-night seat balance failed constraints");
  }
  return {office,seats,called,dem,rep,independent,demLeading,repLeading};
}

/** A site-wide snapshot is not AP's licensed live feed.
 * Read only the source's *actual results* section. Never read projected/forecast balances.
 */
export function parseElectionNightPage(html:string,fetchedAt:string):ElectionNightSnapshot{
  if(html.length>4_000_000)throw new Error("Election-night document too large");
  const $=load(html);
  const text=normalize($("body").text());
  if(!/2026 midterm election results/i.test(text))throw new Error("Page identity mismatch");
  const from=text.indexOf("Balance of power");
  const until=text.indexOf("Control of Congress, live projection",from);
  if(from<0||until<=from)throw new Error("Cannot distinguish actual counts from forecast");
  const balance=text.slice(from,until);
  const offices={
    House:readScoreboard(balance,"House"),
    Senate:readScoreboard(balance,"Senate"),
    Governor:readScoreboard(balance,"Governor")
  };
  const updated=text.match(/Updated (November 3, 2026 at \d{1,2}:\d{2} [AP]M (?:ES|ED)T)/);
  if(!updated)throw new Error("Missing election-night published timestamp");
  const calls:VerifiedCall[]=[];
  const keyStart=text.indexOf("Key races",until);
  const keyEnd=text.indexOf("Close races",keyStart);
  if(keyStart>=0&&keyEnd>keyStart){
    const keyText=text.slice(keyStart,keyEnd);
    // Restrict to exact clearly source-called leaders; do not infer wins from vote percentages.
    const knownStates=["Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana",
    "Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska",
    "Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina","North Dakota","Ohio",
    "Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina","South Dakota","Tennessee","Texas",
    "Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"];
    const statePattern=knownStates.map(s=>s.replace(/ /g,"\\s+")).join("|");
    const rx=new RegExp("("+statePattern+")\\s+(Senate|Governor)\\s+[^✓]{0,80}✓\\s*([A-Za-z. '-]{3,75}?)\\s+(Democratic Party|Republican Party|Independent)\\s+\\d{1,3}(?:\\.\\d+)?%","gi");
    const seen=new Set<string>();
    for(const found of keyText.matchAll(rx)){
      const state=normalize(found[1]),office=found[2].toLowerCase()==="senate"?"Senate" as const:"Governor" as const;
      const k=state+":"+office;
      if(seen.has(k))continue;
      seen.add(k);
      calls.push({state,office,winner:normalize(found[3]),party:found[4]==="Democratic Party"?"D":found[4]==="Republican Party"?"R":"I",sourceUrl:SOURCE});
    }
  }
  return {source:"Poliwave",sourceUrl:SOURCE,sourceUpdated:updated[1],fetchedAt,stale:false,
    headline:"Independent decision-desk race calls, not AP calls or state certification",
    offices,calls};
}
