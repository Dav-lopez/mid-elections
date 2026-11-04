import {NextResponse} from "next/server";
import {parseElectionNightPage,type ElectionNightSnapshot} from "../../../lib/election-night";

export const runtime="nodejs";
export const dynamic="force-dynamic";
const SOURCE="https://www.poliwave.com/us/live/midterms-2026";
const TTL=65_000;
let cache:{expires:number;value:ElectionNightSnapshot}|null=null;
let pending:Promise<ElectionNightSnapshot>|null=null;

async function retrieve():Promise<ElectionNightSnapshot>{
 const response=await fetch(SOURCE,{
  signal:AbortSignal.timeout(13000),
  headers:{"Accept":"text/html","User-Agent":"CivicPulse/1.0 (public election-information viewer)"},
  next:{revalidate:60}
 });
 if(!response.ok)throw new Error("Results website HTTP "+response.status);
 const advertised=Number(response.headers.get("content-length"));
 if(Number.isFinite(advertised)&&advertised>4_000_000)throw new Error("Results document exceeds safety limit");
 const html=await response.text();
 return parseElectionNightPage(html,new Date().toISOString());
}

/** Verified named calls from dated public reporting, retained only as a clearly labeled
 * fallback when the live independent scoreboard is not reachable from our server.
 * Do not derive balance-of-power totals from this selected subset.
 */
const snapshotCalls=[
 {state:"Georgia",office:"Governor",winner:"Keisha Lance Bottoms",party:"D",sourceLabel:"Associated Press report",sourceUrl:"https://apnews.com/article/ef6199e25927a9ac9f4c18eae0e497cd"},
 {state:"North Carolina",office:"Senate",winner:"Roy Cooper",party:"D",sourceLabel:"Associated Press report",sourceUrl:"https://apnews.com/article/ef6199e25927a9ac9f4c18eae0e497cd"},
 {state:"Georgia",office:"Senate",winner:"Jon Ossoff",party:"D",sourceLabel:"Associated Press report",sourceUrl:"https://apnews.com/article/ef6199e25927a9ac9f4c18eae0e497cd"},
 {state:"Florida",office:"Governor",winner:"Byron Donalds",party:"R",sourceLabel:"Associated Press report",sourceUrl:"https://apnews.com/article/ef6199e25927a9ac9f4c18eae0e497cd"},
 {state:"Florida",office:"Senate",winner:"Ashley Moody",party:"R",sourceLabel:"Guardian election-night reporting",sourceUrl:"https://www.theguardian.com/us-news/live/2026/nov/03/midterm-election-results-live-updates"},
 {state:"New Hampshire",office:"Senate",winner:"Chris Pappas",party:"D",sourceLabel:"Guardian election-night reporting",sourceUrl:"https://www.theguardian.com/us-news/live/2026/nov/03/midterm-election-results-live-updates"},
 {state:"Virginia",office:"Senate",winner:"Mark Warner",party:"D",sourceLabel:"Guardian election-night reporting",sourceUrl:"https://www.theguardian.com/us-news/live/2026/nov/03/midterm-election-results-live-updates"},
 {state:"Ohio",office:"Governor",winner:"Amy Acton",party:"D",sourceLabel:"Poliwave decision desk",sourceUrl:"https://www.poliwave.com/us/live/midterms-2026/ohio"},
 {state:"Ohio",office:"Senate",winner:"Sherrod Brown",party:"D",sourceLabel:"Poliwave decision desk",sourceUrl:"https://www.poliwave.com/us/live/midterms-2026/ohio"}
] as const;

const fallback=()=>({
 source:"Dated AP / Guardian / Poliwave reporting",
 sourceUrl:"https://apnews.com/article/ef6199e25927a9ac9f4c18eae0e497cd",
 sourceUpdated:"Reported November 3, 2026; not a live synchronized feed",
 fetchedAt:new Date().toISOString(),
 stale:true,
 sourceUnavailable:true,
 headline:"Selected reported winners only; these are NOT national seat totals or live race-call monitoring",
 offices:null,
 calls:snapshotCalls
});

export async function GET(){
 const headers={"Cache-Control":"public, s-maxage=10, stale-while-revalidate=50"};
 if(cache&&cache.expires>Date.now())return NextResponse.json(cache.value,{headers});
 try{
  pending??=retrieve();
  const value=await pending;
  cache={expires:Date.now()+TTL,value};
  return NextResponse.json(value,{headers});
 }catch{
  if(cache){
   cache.expires=Date.now()+15_000;
   return NextResponse.json({...cache.value,stale:true},{headers:{"Cache-Control":"no-store"}});
  }
  // Explicit fallback: named newsroom calls are real, but not a live automated feed.
  return NextResponse.json(fallback(),{headers:{"Cache-Control":"public, s-maxage=60"}});
 }finally{pending=null;}
}
