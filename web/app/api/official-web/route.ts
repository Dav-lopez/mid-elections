import { NextResponse } from "next/server";
import { marylandHouseUrl, MARYLAND_OFFICIAL_RESULTS_INDEX, parseMarylandHouse, type OfficialPageContest } from "../../../lib/official-web-maryland";

export const runtime="nodejs";
export const dynamic="force-dynamic";
export const maxDuration=30;

type Snapshot={
  contests:Record<string,OfficialPageContest>;
  rosters:Record<string,{authority:string;sourceUrl:string;kind:"ballot";candidates:{n:string;p:string}[]}>;
  sources:{authority:string;url:string;status:"available"|"partial"|"unavailable";details:string};
  fetchedAt:string;
  stale:boolean;
};
let snapshot:{expires:number;data:Snapshot}|null=null;

async function downloadDistrict(district:number):Promise<OfficialPageContest>{
  const url=marylandHouseUrl(district);
  const response=await fetch(url,{
    headers:{"Accept":"text/html","User-Agent":"CivicPulse/1.0 (public election source reader)"},
    signal:AbortSignal.timeout(7000),
    next:{revalidate:180}
  });
  if(!response.ok)throw new Error("Maryland page HTTP "+response.status);
  const length=Number(response.headers.get("content-length"));
  if(Number.isFinite(length)&&length>1_000_000)throw new Error("Maryland page too large");
  const html=await response.text();
  return parseMarylandHouse(html,district);
}

export async function GET(){
  if(snapshot && Date.now()<snapshot.expires){
    return NextResponse.json(snapshot.data,{headers:{"Cache-Control":"public, s-maxage=60, stale-while-revalidate=60"}});
  }
  // Four concurrent requests max, to avoid hammering state infrastructure.
  const districts=[1,2,3,4,5,6,7,8];
  const output:PromiseSettledResult<OfficialPageContest>[]=[];
  for(let i=0;i<districts.length;i+=4){
    const results=await Promise.allSettled(districts.slice(i,i+4).map(downloadDistrict));
    output.push(...results);
  }
  const contests:Snapshot["contests"]={};
  const rosters:Snapshot["rosters"]={};
  for(const result of output){
    if(result.status!=="fulfilled")continue;
    const race=result.value;
    contests["House:"+race.seat]=race;
    rosters["House:"+race.seat]={
      authority:"Maryland State Board of Elections",
      sourceUrl:race.sourceUrl,
      kind:"ballot",
      candidates:race.cands.map(candidate=>({n:candidate.n,p:candidate.p}))
    };
  }
  const successful=Object.keys(contests).length;
  const data:Snapshot={
    contests,rosters,
    sources:{
      authority:"Maryland State Board of Elections",
      url:MARYLAND_OFFICIAL_RESULTS_INDEX,
      status:successful===8?"available":successful>0?"partial":"unavailable",
      details:successful+"/8 congressional district pages parsed"
    },
    fetchedAt:new Date().toISOString(),
    stale:false
  };
  if(successful===0){
    // Preserve last valid data if the state website becomes inaccessible.
    if(snapshot){
      snapshot={expires:Date.now()+60_000,data:{...snapshot.data,stale:true,
        sources:{...snapshot.data.sources,status:"unavailable",details:"Site unavailable; showing previously validated snapshot"}}};
      return NextResponse.json(snapshot.data,{headers:{"Cache-Control":"no-store"}});
    }
    return NextResponse.json({error:"Maryland election website unavailable",source:MARYLAND_OFFICIAL_RESULTS_INDEX},{status:502});
  }
  snapshot={expires:Date.now()+180_000,data};
  return NextResponse.json(data,{headers:{"Cache-Control":"public, s-maxage=60, stale-while-revalidate=60"}});
}
