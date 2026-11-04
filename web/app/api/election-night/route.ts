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
  return NextResponse.json({error:"Independent called-seat source unavailable",source:SOURCE},
    {status:502,headers:{"Cache-Control":"no-store"}});
 }finally{pending=null;}
}
