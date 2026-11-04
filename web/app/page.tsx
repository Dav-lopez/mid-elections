"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import "./dashboard.css";
import { officialRosters } from "../lib/official-rosters";
import UsMap from "../components/us-map";
import { partyCode, partyLabel, raceInsight, sourceCalledParty, providerSeatKey } from "../lib/race-insights";

type Candidate = { n?: string; p?: string; v?: number | null; pct?: number | null };
type Race = { cands?: Candidate[]; total?: number | null; pct_in?: number | null; leader?: string | null; winner?: string | null; called?: boolean };
type Feed = { api: number; year: number; office: string; live: boolean; stale: boolean; counting: boolean; final: boolean; as_of: string | null; source: string; races: Record<string, Race> };
type Office = "House" | "Senate" | "Governor";
type CandidateSource = { authority: string; status: string; url: string };
type DynamicRoster = { authority: string; sourceUrl: string; kind: "ballot" | "filing"; candidates: {n:string;p:string}[] };
type WebContest = { seat:string; cands:Candidate[]; total:number|null; pct_in:number|null; called:false; winner:""; sourceUrl:string; updatedLabel:string|null };
type WebSourceStatus = {authority:string;url:string;status:string;details:string};
type NightOffice = "Senate"|"House"|"Governor";
type NightTotal = {office:NightOffice;seats:number;called:number;dem:number;rep:number;independent?:number;demLeading:number;repLeading:number};
type NightCall = {office:NightOffice;state:string;district?:string;winner:string;party:string;sourceUrl:string;sourceLabel?:string};
type NightResult = {source:string;sourceUrl:string;sourceUpdated:string;stale:boolean;sourceUnavailable?:boolean;headline:string;offices:Record<NightOffice,NightTotal>|null;calls:NightCall[]};
const API = "/api/elections";
const stateNamesByCode:Record<string,string> = { AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};
const states = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
// Coverage listed in the current public feed registry, not a statement about election-day turnout.
const supportedResultsStates = new Set("AR AZ CO CT FL GA IA ID IN LA MI MN NC PA RI SC TX UT VA VT WA WV".split(" "));
const house: Record<string,number> = {AL:7,AK:1,AZ:9,AR:4,CA:52,CO:8,CT:5,DE:1,FL:28,GA:14,HI:2,ID:2,IL:17,IN:9,IA:4,KS:4,KY:6,LA:6,ME:2,MD:8,MA:9,MI:13,MN:8,MS:4,MO:8,MT:2,NE:3,NV:4,NH:2,NJ:12,NM:3,NY:26,NC:14,ND:1,OH:15,OK:5,OR:6,PA:17,RI:2,SC:7,SD:1,TN:9,TX:38,UT:4,VT:1,VA:11,WA:10,WV:2,WI:8,WY:1};
const senate = "AL AK AR CO DE GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OK OR RI SC SD TN TX VA WV WY".split(" ");
const seats = [...Object.entries(house).flatMap(([state,n])=>Array.from({length:n},(_,i)=>({office:"House" as Office,state,key:state+"-"+(n===1?"00":String(i+1).padStart(2,"0"))}))),...senate.map(state=>({office:"Senate" as Office,state,key:state})),...["FL","OH"].map(state=>({office:"Senate" as Office,state,key:state+"-SPECIAL"}))];
const validVotes=(x:unknown):x is number=>typeof x==="number"&&Number.isSafeInteger(x)&&x>=0;
const nfmt=(x:unknown)=>validVotes(x)?x.toLocaleString("en-US"):"Not reported";
const clean=(s:unknown)=>typeof s==="string"?s.slice(0,120):"";
const baseUrl=(year:number,office:Office)=>API+"?year="+year+"&office="+office;
const partyClass=(party:unknown)=>({D:"party-dem",R:"party-rep",I:"party-ind",L:"party-lib",G:"party-green"} as Record<string,string>)[partyCode(party)]??"party-other";
export default function Home(){
  const [year,setYear]=useState(2026);
  const [country,setCountry]=useState<"US"|"NG">("US");
  const [office,setOffice]=useState<"Both"|Office>("Both");
  const [state,setState]=useState("All");
  const [search,setSearch]=useState("");
  const [feeds,setFeeds]=useState<Partial<Record<Office,Feed>>>({});
  const [errors,setErrors]=useState<Partial<Record<Office,string>>>({});
  const [checked,setChecked]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [refresh,setRefresh]=useState(0);
  const [closeAlert,setCloseAlert]=useState(false);
  const [mapMode,setMapMode]=useState<"coverage"|"senate-leaders"|"senate-called">("senate-called");
  const seenCloseRaces=useRef("");
  const [externalRosters,setExternalRosters]=useState<Record<string,DynamicRoster>>({});
  const [candidateSources,setCandidateSources]=useState<CandidateSource[]>([]);
  const [candidateError,setCandidateError]=useState("");
  const [candidatesChecked,setCandidatesChecked]=useState<string|null>(null);
  const [webContests,setWebContests]=useState<Record<string,WebContest>>({});
  const [webSource,setWebSource]=useState<WebSourceStatus|null>(null);
  const [webSourceChecked,setWebSourceChecked]=useState<string|null>(null);
  const [webSourceError,setWebSourceError]=useState("");
  const [webSourceStale,setWebSourceStale]=useState(false);
  const [nightTab,setNightTab]=useState<NightOffice>("Senate");
  const [showAllCalls,setShowAllCalls]=useState(false);
  const [night,setNight]=useState<NightResult|null>(null);
  const [nightError,setNightError]=useState("");
  const [nightChecked,setNightChecked]=useState<string|null>(null);
  useEffect(()=>{
    if(country!=="US"){setFeeds({});setErrors({});setBusy(false);return;}
    let cancelled=false;
    let pending=false;
    let activeController:AbortController|null=null;
    const get=async()=>{
      if(pending || cancelled)return;
      pending=true;
      setBusy(true);
      const controller=new AbortController();
      activeController=controller;
      const results=await Promise.all((["House","Senate","Governor"] as Office[]).map(async o=>{
        try {
          const response=await fetch(baseUrl(year,o),{cache:"no-store",headers:{"Accept":"application/json"},signal:controller.signal});
          if(!response.ok)throw new Error("HTTP "+response.status);
          const data:unknown=await response.json();
          if(!data||typeof data!=="object")throw new Error("Invalid feed");
          const f=data as Feed;
          if(f.api!==1||f.year!==year||f.office.toLowerCase()!==o.toLowerCase()||typeof f.races!=="object"||f.races===null||Array.isArray(f.races)||typeof f.live!=="boolean"||typeof f.stale!=="boolean"||typeof f.counting!=="boolean"||typeof f.final!=="boolean")throw new Error("Feed failed metadata validation");
          return {office:o,feed:f,error:null};
        }catch(e){return {office:o,feed:null,error:e instanceof Error?e.message:"Request failed"};}
      }));
      pending=false;
      if(cancelled)return;
      activeController=null;
      setFeeds(prev=>{const next={...prev};for(const r of results){if(r.feed)next[r.office]=r.feed;else if(prev[r.office]?.year!==year)delete next[r.office];}return next;});
      setErrors(Object.fromEntries(results.filter(r=>r.error).map(r=>[r.office,r.error])) as Partial<Record<Office,string>>);
      setChecked(new Date().toISOString());
      setBusy(false);
    };
    void get();
    // A five-second on-screen check; never overlap slow requests or poll hidden tabs.
    const timer=setInterval(()=>{if(document.visibilityState==="visible")void get();},5000);
    const onVisible=()=>{if(document.visibilityState==="visible")void get();};
    document.addEventListener("visibilitychange",onVisible);
    return ()=>{cancelled=true;activeController?.abort();clearInterval(timer);document.removeEventListener("visibilitychange",onVisible);};
  },[year,country,refresh]);
  useEffect(()=>{
    if(country!=="US" || year!==2026) return;
    let cancelled=false;
    const check=async()=>{
      try{
        const response=await fetch("/api/candidates",{cache:"no-store"});
        if(!response.ok) throw new Error("Candidate-source endpoint returned HTTP "+response.status);
        const data:unknown=await response.json();
        if(!data || typeof data!=="object") throw new Error("Invalid candidate-source response");
        const payload=data as {rosters?:Record<string,DynamicRoster>;sources?:CandidateSource[]};
        if(!cancelled){
          setExternalRosters(payload.rosters??{});
          setCandidateSources(payload.sources??[]);
          setCandidateError("");
          setCandidatesChecked(new Date().toISOString());
        }
      }catch(error){
        if(!cancelled)setCandidateError(error instanceof Error?error.message:"Candidate-source request failed");
      }
    };
    void check();
    const timer=setInterval(()=>void check(),60*60*1000);
    return ()=>{cancelled=true;clearInterval(timer);};
  },[year,country]);
  // Separate official webpage ingestion from provider JSON and federal filings.
  // These pages contain verified ballot names even while vote totals say "NR".
  useEffect(()=>{
    if(country!=="US"||year!==2026)return;
    let cancelled=false;
    let checking=false;
    const get=async()=>{
      if(cancelled||checking)return;
      checking=true;
      try{
        const response=await fetch("/api/official-web",{cache:"no-store"});
        if(!response.ok)throw new Error("HTTP "+response.status);
        const payload:unknown=await response.json();
        if(!payload||typeof payload!=="object")throw new Error("Invalid official web response");
        const parsed=payload as {contests?:Record<string,WebContest>;sources?:WebSourceStatus;stale?:boolean;fetchedAt?:string};
        if(!parsed.contests||typeof parsed.contests!=="object")throw new Error("No web race data");
        if(!cancelled){
          setWebContests(parsed.contests);
          setWebSource(parsed.sources??null);
          setWebSourceChecked(parsed.fetchedAt??new Date().toISOString());
          setWebSourceStale(parsed.stale===true);
          setWebSourceError("");
        }
      }catch(error){
        if(!cancelled){setWebSourceError(error instanceof Error?error.message:"Web source request failed");setWebSourceStale(true);}
      }finally{checking=false;}
    };
    void get();
    // State website is checked at most every three minutes, never every five seconds.
    const timer=setInterval(()=>{if(document.visibilityState==="visible")void get();},180000);
    return ()=>{cancelled=true;clearInterval(timer);};
  },[country,year]);
  useEffect(()=>{
    if(country!=="US"||year!==2026)return;
    let cancelled=false;
    let pending=false;
    const get=async()=>{
      if(cancelled||pending)return;
      pending=true;
      try{
        const response=await fetch("/api/election-night",{cache:"no-store"});
        if(!response.ok)throw new Error("HTTP "+response.status);
        const source:unknown=await response.json();
        if(!source||typeof source!=="object")throw new Error("Unrecognized election-night response");
        const data=source as NightResult;
        if(!Array.isArray(data.calls)||!data.sourceUpdated||!data.sourceUrl)throw new Error("Invalid election-night result");
        if(!cancelled){setNight(data);setNightError("");setNightChecked(new Date().toISOString());}
      }catch(e){if(!cancelled)setNightError(e instanceof Error?e.message:"Could not retrieve election-night results");}
      finally{pending=false;}
    };
    void get();
    // Screen checks every five seconds elsewhere; race-call provider is polled once per minute.
    const timer=setInterval(()=>{if(document.visibilityState==="visible")void get();},60000);
    return ()=>{cancelled=true;clearInterval(timer);};
  },[year,country]);
  const rows=useMemo(()=>{
    if(country!=="US")return [];
    const providerContests=Object.values(feeds).flatMap(f=>f&&f.year===year?Object.keys(f.races).map(key=>({office:f.office as Office,state:key.slice(0,2).toUpperCase(),key:key.replace(/-special$/i,"-SPECIAL")})):[]);
    // Governor contests are added only when the provider actually reports them.
    const registry=year===2026?[...seats,...providerContests.filter(r=>r.office==="Governor")]:providerContests;
    return registry.map(s=>{
      const f=feeds[s.office]?.year===year?feeds[s.office]:undefined;
      const web=year===2026?webContests[s.office+":"+s.key]:undefined;
      // The published Senate-special feed key is "FL-special" / "OH-special".
      const publishedKey=providerSeatKey(s.office,s.key);
      const race:Race|null=f?.races?.[s.key]??f?.races?.[publishedKey]??(web?{
        cands:web.cands,total:web.total,pct_in:web.pct_in,called:false,winner:""
      }:null);
      const feedCandidates=Array.isArray(race?.cands)?race.cands.filter(c=>c&&typeof c.n==="string"):[];
      const remote=year===2026?externalRosters[s.office+":"+s.key]:undefined;
      const manual=year===2026?officialRosters[s.office+":"+s.key]:undefined;
      const webRoster=web?{authority:"Maryland State Board of Elections",sourceUrl:web.sourceUrl,kind:"ballot" as const,candidates:web.cands.map(c=>({n:c.n??"",p:c.p??""}))}:undefined;
      const roster=webRoster??(remote?.kind==="ballot"?remote:manual?{...manual,kind:"ballot" as const}:remote);
      const candidates=feedCandidates.length?feedCandidates:(roster?.candidates.map(c=>({...c,v:null,pct:null}))??[]);
      const reported=validVotes(race?.total)&&race.total>0||candidates.some(c=>validVotes(c.v)&&c.v>0);
      const insight=raceInsight(race);
      return {...s,race,candidates,reported,roster,feed:f,insight,webSourceUrl:web?.sourceUrl,webUpdated:web?.updatedLabel};
    });
  },[country,year,feeds,externalRosters,webContests]);
  const filtered=rows.filter(r=>(office==="Both"||r.office===office)&&(state==="All"||r.state===state)&&(!search||r.key.toLowerCase().includes(search.toLowerCase())||r.candidates.some(c=>clean(c.n).toLowerCase().includes(search.toLowerCase()))));
  const listed=rows.filter(r=>r.race).length,reported=rows.filter(r=>r.reported).length;
  const currentFeeds=Object.values(feeds).filter((f):f is Feed=>Boolean(f&&f.year===year));
  const live=currentFeeds.some(f=>f.live);
  const counting=currentFeeds.some(f=>f.counting);
  const stale=currentFeeds.some(f=>f.stale);
  const allFinal=currentFeeds.length>0&&currentFeeds.every(f=>f.final);
  const hasSourceErrors=Object.values(errors).some(Boolean);
  // Election Day is not the same as an active vote feed. Show both truthfully.
  const feedStatus=country!=="US"?"No connected results source":year===2024?"Historical results archive":
    live?"Live votes reporting":stale&&counting?"Votes published · delayed feed":
    allFinal&&counting?"Reported precincts complete":
    counting?"Votes published · updating":
    currentFeeds.length===0?(busy?"Connecting to results feed":"Results feed unavailable"):
    "Awaiting first published votes";
  const reportingSources=(["House","Senate","Governor"] as Office[]).map(o=>{
    const feed=feeds[o]?.year===year?feeds[o]:undefined;
    const raceCount=feed?Object.keys(feed.races).length:0;
    return {office:o,loaded:!!feed,raceCount,counting:feed?.counting??false,
      live:feed?.live??false,stale:feed?.stale??false,asOf:feed?.as_of??null};
  });

  const closeContests=rows.filter(r=>r.insight.close).sort((a,b)=>(a.insight.marginPct??100)-(b.insight.marginPct??100));
  const calledContests=rows.filter(r=>r.insight.sourceCalledWinner!==null);
  const leadingContests=rows.filter(r=>r.insight.leader!==null);
  const calledByParty=(code:string)=>calledContests.filter(r=>sourceCalledParty(r.race)===code).length;
  const visibleClose=closeContests.filter(r=>state==="All"||r.state===state);
  const closeSignature=year===2026&&country==="US"?closeContests.map(r=>r.office+":"+r.key).join("|"):"";
  useEffect(()=>{
    if(closeSignature && closeSignature!==seenCloseRaces.current)setCloseAlert(true);
    seenCloseRaces.current=closeSignature;
  },[closeSignature]);
  const chooseRace=(r:{office:Office;state:string})=>{setOffice(r.office);setState(r.state);setSearch("");setCloseAlert(false);};
  const featuredKeys = ["IA", "OH-SPECIAL", "MD-01", "MD-08", "KS", "NC", "TX", "GA", "FL-SPECIAL", "MI"];
  const featured = (year === 2026 && state === "All" && !search
    ? [...new Set([...closeContests.slice(0,6).map(r=>r.key),...calledContests.slice(0,6).map(r=>r.key),...featuredKeys])]
      .flatMap(key=>rows.filter(r=>r.key===key && (office==="Both"||office===r.office)))
    : filtered.filter(r=>r.race || year===2026)
  ).slice(0,12);
  const mapCounts = Object.fromEntries(states.map(code=>{
    const contests=rows.filter(r=>r.state===code && (office==="Both"||r.office===office));
    return [code,{reported:contests.filter(r=>r.reported).length,listed:contests.filter(r=>r.race||r.roster).length,tracked:contests.length}];
  })) as Record<string,{reported:number;listed:number;tracked:number}>;
  // Never color a whole state by a House district, filings, predictions, or an ambiguous Senate contest.
  const senateLeadByState=Object.fromEntries(states.flatMap(code=>{
    const reportedSenate=rows.filter(r=>r.state===code&&r.office==="Senate"&&r.insight.leader);
    if(reportedSenate.length!==1)return [];
    const race=reportedSenate[0],leader=race.insight.leader!;
    if(typeof leader.v!=="number"||!Number.isSafeInteger(leader.v)||leader.v<=0)return [];
    return [[code,{name:clean(leader.n),party:partyCode(leader.p),seat:race.key,votes:leader.v}]];
  })) as Record<string,{name:string;party:string;seat:string;votes:number}>;
  const senateStatesReporting=Object.keys(senateLeadByState).length;
  const nightTotals=night?.offices?.[nightTab]??null;
  const trackedOfficeCalls=night?.calls.filter(c=>c.office===nightTab)??[];
  const trackedDem=trackedOfficeCalls.filter(c=>partyCode(c.party)==="D").length;
  const trackedRep=trackedOfficeCalls.filter(c=>partyCode(c.party)==="R").length;
  const nightCalls=trackedOfficeCalls.filter(c=>state==="All"||stateNamesByCode[state]===c.state);
  const nightProgress=nightTotals?Math.max(0,Math.min(100,(nightTotals.dem+nightTotals.rep+(nightTotals.independent??0))/nightTotals.seats*100)):0;
  const senateWinners=Object.fromEntries((night?.calls??[]).filter(c=>c.office==="Senate").flatMap(c=>{
    const code=Object.keys(stateNamesByCode).find(k=>stateNamesByCode[k]===c.state);
    return code?[[code,{name:c.winner,party:partyCode(c.party),source:c.sourceLabel??night?.source??"independent decision desk"}]]:[];
  })) as Record<string,{name:string;party:string;source:string}>;
  const dataPublished = reported>0;
  return <main className="dashboard">
    <header className="hero"><div className="eyebrow">CIVICPULSE · SOURCE-AWARE ELECTION INFORMATION</div><h1>Election Results Dashboard</h1><p>Official-source reporting where available. No forecasts, invented totals, or inferred winners.</p><div className="topline"><span>{country==="US"?"United States":"Nigeria"}</span><span>{country==="US"?year:2027} election coverage</span><span>{feedStatus}</span></div></header>
    <div className="controls"><label>Country<select value={country} onChange={e=>{setCountry(e.target.value as "US"|"NG");setState("All")}}><option value="US">United States</option><option value="NG">Nigeria</option></select></label><label>Election<select value={country==="US"?year:2027} disabled={country==="NG"} onChange={e=>setYear(Number(e.target.value))}><option value={2026}>2026 Congressional</option><option value={2024}>2024 Historical replay</option></select></label><button onClick={()=>setRefresh(v=>v+1)} disabled={busy||country!=="US"}>{busy?"Checking source…":"Refresh source"}</button></div>
    {country==="US"&&<div className="refresh-status" role="status"><i className="dot" aria-hidden="true"/> Auto-check every 5 seconds while this tab is visible · Provider snapshot refresh is cached for 30 seconds · Last check: {checked?new Date(checked).toLocaleTimeString():"Pending"}{busy?" · Fetching…":""}</div>}
    {country==="NG"?<section className="notice"><h2>Nigeria 2027 · Integration pending</h2><p>INEC-backed election feeds and validated candidate rosters are not connected yet. No Nigerian vote totals are displayed.</p></section>:<>
    {year===2026&&<section className="night-balance" aria-label="Election night source-attributed seat balance and winner reports">
      <div className="night-balance-heading"><div><h2>2026 election night</h2><p className="night-balance-sub"><i className={"night-live-dot"+(!night||night.stale?" night-dot-delayed":"")} aria-hidden="true"/>{night?.stale?"Dated winner reports · not a live calls feed":"Source-aware winner calls · five-second vote checks"}</p></div><a href="https://www.theguardian.com/us-news/ng-interactive/2026/nov/03/midterm-elections-full-results-senate-house-governor-races" target="_blank" rel="noreferrer">Full AP-powered results ↗</a></div>
      <div className="night-chamber-tabs" role="group" aria-label="Election night office">
        {(["Senate","House","Governor"] as const).map(chamber=><button key={chamber} type="button" aria-pressed={nightTab===chamber} onClick={()=>setNightTab(chamber)}>{chamber}</button>)}
      </div>
      {nightTotals?<><div className="night-summary">
        <div className="side dem"><span className="count">{nightTotals.dem}</span><span className="side-label">Democratic</span></div>
        <div className="center"><strong>{nightTab==="House"?"218":nightTab==="Senate"?"51":"—"}</strong><span>{nightTab==="Governor"?"Nationwide governorships": "For majority"}<br/>{nightTotals.called} of {nightTab==="House"?435:nightTab==="Senate"?35:36} races called</span></div>
        <div className="side rep"><span className="count">{nightTotals.rep}</span><span className="side-label">Republican</span></div>
      </div>
      <div className="night-bar" role="img" aria-label={nightTotals.dem+" Democratic seats and "+nightTotals.rep+" Republican seats recorded by "+(night?.source??"verified provider")}>
        <div className="dem-fill" style={{width:nightTotals.dem/nightTotals.seats*100+"%"}}/>
        <div className="unfilled" />
        <div className="rep-fill" style={{width:nightTotals.rep/nightTotals.seats*100+"%"}}/>
      </div>
      <div className="night-summary-foot"><span>{nightTotals.demLeading} more D-leading</span><span>{nightTotals.independent?"Independent: "+nightTotals.independent+" · ":""}{Math.round(nightProgress)}% seats assigned or not up</span><span>{nightTotals.repLeading} more R-leading</span></div></>:
        <div className="night-partial">
          <div className="night-summary" aria-label="Verified winner calls in connected sources, not nationwide seat totals">
            <div className="side dem"><span className="count">{trackedDem}</span><span className="side-label">D calls tracked</span></div>
            <div className="center"><strong>{trackedOfficeCalls.length}</strong><span>named source calls<br/>partial coverage</span></div>
            <div className="side rep"><span className="count">{trackedRep}</span><span className="side-label">R calls tracked</span></div>
          </div>
          {trackedOfficeCalls.length>0&&<div className="night-bar" role="img" aria-label={trackedDem+" Democratic and "+trackedRep+" Republican named calls in this partial source"}>
            <div className="dem-fill" style={{width:trackedDem/trackedOfficeCalls.length*100+"%"}}/>
            <div className="unfilled"/>
            <div className="rep-fill" style={{width:trackedRep/trackedOfficeCalls.length*100+"%"}}/>
          </div>}
          <p className="night-alert">These counts cover <strong>only the races named by the currently connected reporting source</strong>. They are not the national Senate, House, or governor balance, and cannot establish chamber control. No missing seat is counted as zero. <a href="https://www.theguardian.com/us-news/ng-interactive/2026/nov/03/midterm-elections-full-results-senate-house-governor-races" target="_blank" rel="noreferrer">View nationwide AP-powered results</a>.</p>
        </div>}
      <p className="night-source">Source: <a href={night?.sourceUrl??"https://www.poliwave.com/us/live/midterms-2026"} target="_blank" rel="noreferrer">{night?.source??"Independent election-night results"}</a> · {night?.sourceUpdated??"Source check pending"} · {night?.stale?"Delayed / not synchronized live":"Source snapshot"}{nightChecked?" · Checked "+new Date(nightChecked).toLocaleTimeString():""}.</p>
      {nightError&&<p className="warning">Winner-source connection: {nightError}</p>}
      {night?.sourceUnavailable&&<p className="warning">Live automated winner feed is unavailable. The names below are dated, independently reported calls—not a continuously updated AP feed.</p>}
      <div className="night-winners">
        {nightCalls.slice(0,showAllCalls?nightCalls.length:8).map((call,i)=><div className="night-winner" key={call.state+call.office+call.winner+i}>
          <small>{call.state} · {call.office}{call.district?" · District "+Number(call.district):""}</small>
          <span className="candidate-party"><span className={"party-badge "+partyClass(call.party)}>{partyCode(call.party)}</span><strong>{call.winner}</strong></span>
          <span className="night-status">SOURCE-CALLED · NOT CERTIFIED</span>
          <a href={call.sourceUrl} target="_blank" rel="noreferrer" className="party-caption">{call.sourceLabel??night?.source??"Source"} · View report ↗</a>
        </div>)}
        {nightCalls.length===0&&<p className="muted">No named calls available for this office and state from the connected sources. <a target="_blank" rel="noreferrer" href="https://www.theguardian.com/us-news/ng-interactive/2026/nov/03/midterm-elections-full-results-senate-house-governor-races">Review the live AP-powered results</a>.</p>}
      </div>
      {nightCalls.length>8&&<button className="show-more-calls" type="button" onClick={()=>setShowAllCalls(x=>!x)} aria-expanded={showAllCalls}>{showAllCalls?"Show fewer": "Show all "+nightCalls.length+" attributed calls"}</button>}
    </section>}
    <section className="metrics"><article><span>Tracked contests</span><strong>{rows.length.toLocaleString()}</strong></article><article><span>Listed by provider</span><strong>{listed.toLocaleString()}</strong></article><article><span>Contests with votes</span><strong>{reported.toLocaleString()}</strong></article><article><span>Feed status</span><strong className="feed-status-value">{feedStatus}</strong></article></section>
    <section className="notice"><strong>{year===2024?"Historical 2024 vote totals — not 2026 results.":"2026 general election · November 3, 2026"}</strong><p>Counts are displayed only when published by the source. Missing results are not zero. Precinct completion does not mean certification. A vote leader is not necessarily a winner.</p><p>Source: <a href="https://openamerica.io/elections/api/" target="_blank" rel="noreferrer">Open America election API, relaying state election-office counts</a>. Publisher timestamp: {Object.values(feeds).filter(f=>f?.year===year&&f.as_of).map(f=>f?.office+": "+new Date(f!.as_of!).toLocaleString()).join(" · ")||"Not published"}. Last checked: {checked?new Date(checked).toLocaleString():"Not checked"}.</p>{Object.entries(errors).map(([o,error])=><p className="warning" key={o}>{o}: source unavailable ({error}). Previously retrieved data may be stale.</p>)}</section>
    <section className="notice" aria-label="Results provider reporting status">
      <strong>Connected results-feed status by office</strong>
      <p className="feed-clarification">{counting?"Published votes are available for at least one connected race.":hasSourceErrors&&currentFeeds.length===0?"The upstream results feed could not be loaded; check the errors below.":"Voting may be underway, but the connected source has not yet published vote totals. The first U.S. poll closures begin at 5 p.m. Central; results can take additional time to arrive."} The dashboard checks every five seconds; the provider may update and cache only every 30–60 seconds.</p>
      <p className="muted">To inspect the raw response directly: <a href="/api/elections?year=2026&office=House" target="_blank" rel="noreferrer">House results JSON</a> · <a href="/api/elections?year=2026&office=Senate" target="_blank" rel="noreferrer">Senate results JSON</a> · <a href="/api/elections?year=2026&office=Governor" target="_blank" rel="noreferrer">Governor results JSON</a>.</p>
      <p>Provider coverage is partial (22 states). A successful check with zero races means the provider has not yet published matching returns; it does not mean zero votes. Reported totals update only when upstream state results change.</p>
      {state!=="All"&&!supportedResultsStates.has(state)&&!Boolean(Object.keys(webContests).some(key=>key.startsWith("House:"+state+"-")))&&<p className="warning">{state} is outside this provider's 22-state automated results coverage. Candidates may still be listed from government filings; this is not an indication that no one has voted.</p>}
      <div className="source-grid">{reportingSources.map(source=><div key={source.office} className="source-item">
        <strong>{source.office}</strong>
        <span>{!source.loaded?"Unavailable":source.raceCount+" published contests"}</span>
        <span>{source.live?"Live reporting":source.stale?"Stale publication":source.counting?"Published counts (not live)":"Awaiting results"}</span>
        <span>Source timestamp: {source.asOf?new Date(source.asOf).toLocaleString():"Not yet published"}</span>
      </div>)}</div>
      <p className="muted">The five-second dashboard check does not create new counts. The upstream feed is cached and recommends polling once a minute while live. This provider does not declare seat winners.</p>
    </section>
    {year===2026&&<section className="notice" aria-label="Candidate source provenance">
      <strong>Candidate names and parties are independent of vote counting.</strong>
      <p>State ballot lists take precedence over FEC candidate filings. FEC filings may include primary candidates, withdrawn candidates, or people not on the November ballot; they are <strong>not verified ballot rosters</strong>.</p>
      <p>Candidate-source contests: {rows.filter(r=>r.roster).length}. Data checked: {candidatesChecked?new Date(candidatesChecked).toLocaleString():"Pending"}.</p>
      {candidateSources.map(source=><p key={source.authority}><a href={source.url} target="_blank" rel="noreferrer">{source.authority}</a>: {source.status==="available"?"Source loaded":"Source unavailable — retained local rosters remain visible"}</p>)}
      {candidateError&&<p className="warning">Candidate-source warning: {candidateError}</p>}
      <p>Official webpages: {webSource?<>
        <a href={webSource.url} target="_blank" rel="noreferrer">{webSource.authority}</a>
        {" · "}{webSource.details}{" · "}
        {webSourceStale?"Last successful webpage snapshot is stale":webSource.status}
      </>:"Checking Maryland state results pages…"}
      {webSourceChecked?" · Checked "+new Date(webSourceChecked).toLocaleString():""}</p>
      {webSourceError&&<p className="warning">Official webpage source warning: {webSourceError}</p>}
    </section>}
    <section className="insights-board" aria-label="Reported election leaders, close races, and source calls">
      <div className="insight-panel">
        <h3>Reported leaders <span className="party-caption">({leadingContests.length} contests)</span></h3>
        <p>Leading means ahead in currently published candidate votes. Not a projection or a winner declaration.</p>
        {leadingContests.length===0?<p>No candidate vote leader has been published yet.</p>:leadingContests.filter(r=>state==="All"||r.state===state).slice(0,5).map(r=><div className="insight-entry" key={r.office+r.key}>
          <button type="button" onClick={()=>chooseRace(r)}>{r.key} · {r.office}</button>
          <span className={"party-badge "+partyClass(r.insight.leader?.p)} title={partyLabel(r.insight.leader?.p)}>{partyCode(r.insight.leader?.p)}</span>
          <span className="insight-sub">{clean(r.insight.leader?.n)}{r.insight.voteMargin!==null?" · +"+nfmt(r.insight.voteMargin):""}</span>
        </div>)}
      </div>
      <div className="insight-panel">
        <h3>Close races <span className="party-caption">({closeContests.length} reported)</span></h3>
        <p>Reported top-two vote margin is at most 2% of the source's race total; excludes contests already called by the source.</p>
        {closeContests.length===0?<p>No close races are currently substantiated by published totals.</p>:<><button type="button" className="race-alert-button" onClick={()=>setCloseAlert(true)}>Show close-race popup</button>{visibleClose.slice(0,5).map(r=><div className="insight-entry" key={r.office+r.key}>
          <button type="button" onClick={()=>chooseRace(r)}>{r.key} · {r.office}</button>
          <span className="insight-sub">{r.insight.marginPct?.toFixed(2)}% · {nfmt(r.insight.voteMargin)} votes</span>
        </div>)}</>}
      </div>
      <div className="insight-panel">
        <h3>Source-called seats <span className="party-caption">({calledContests.length})</span></h3>
        <p>House: {calledContests.filter(r=>r.office==="House").length} · Senate: {calledContests.filter(r=>r.office==="Senate").length}.</p><p>Source-called seats by verified reported candidate party: Democratic {calledByParty("D")} · Republican {calledByParty("R")} · Other or unmatched {calledContests.length-calledByParty("D")-calledByParty("R")}. Partial provider coverage; not national seat control or certification.</p>
        {calledContests.length===0?<p>No seat winners have been explicitly called by the current source.</p>:calledContests.filter(r=>state==="All"||r.state===state).slice(0,5).map(r=><div className="insight-entry" key={r.office+r.key}>
          <button type="button" onClick={()=>chooseRace(r)}>{r.key} · {r.office}</button>
          <span className={"party-badge "+partyClass(sourceCalledParty(r.race))} title={partyLabel(sourceCalledParty(r.race))}>{partyCode(sourceCalledParty(r.race))}</span><span className="insight-sub">{clean(r.insight.sourceCalledWinner)}</span>
        </div>)}
      </div>
    </section>
    <section className="live-board" aria-label="Election race cards and state map">
      <div className="sectionheading"><div><span className="section-kicker">ELECTION NIGHT BOARD</span><h2>{year===2024?"2024 published results":"2026 midterm elections"}</h2><p>{year===2024?"Historical state-published totals, not a 2026 forecast":"November 3, 2026 · official vote counts appear as they are published"}</p></div><span className={live?"live-tag counting":"live-tag"}>{feedStatus.toUpperCase()}</span></div>
      <div className="chamber-tabs" role="group" aria-label="Filter by chamber">
        {(["Senate","House","Governor","Both"] as const).map(o=><button key={o} type="button" aria-pressed={office===o} className={office===o?"selected":""} onClick={()=>setOffice(o)}>{o==="Both"?"All contests":o}</button>)}
        <span className="tab-note">Governor results appear where the connected provider publishes them.</span>
      </div>
      <div className="race-carousel" aria-label="Featured races">
        {featured.length ? featured.map(r=><article className="race-card" key={r.office+r.key}>
          <div className="race-card-top"><span>{r.state} · {r.office==="Senate"?"U.S. Senate":r.office==="Governor"?"Governor":"U.S. House"}</span><span className="small-date">{year===2024?"2024 archive":"Nov 3"}</span></div>
          <h3>{r.office==="Governor"?r.state+" Governor":r.key.endsWith("-SPECIAL")?r.state+" Senate special":r.key}</h3>
          <div className="race-status">{r.reported?"Votes reported":r.race?"Listed · no votes":r.roster?(r.roster.kind==="filing"?"FEC filings · ballot status unverified":"Official candidate list · no votes"):"Awaiting source publication"}</div>
          {r.insight.sourceCalledWinner?<span className="race-indicator called">Source called: {clean(r.insight.sourceCalledWinner)} · not certified</span>:r.insight.leader?<span className={"race-indicator "+(r.insight.close?"close":"leader")}>{r.insight.close?"CLOSE · ":"Leading · "}{clean(r.insight.leader.n)}{r.insight.voteMargin!==null?" by "+nfmt(r.insight.voteMargin)+" votes":""}{r.insight.marginPct!==null?" ("+r.insight.marginPct.toFixed(2)+"%)":""}</span>:null}
          {r.candidates.length>0 ? <div className="card-candidates">
            {r.candidates.slice(0,3).map((c,i)=><div className="card-candidate" key={r.key+String(i)}>
              <span className={"party-dot "+partyClass(c.p)} title={partyLabel(c.p)} aria-label={"Party: "+partyLabel(c.p)}>{partyCode(c.p)}</span>
              <span className="candidate-name" title={clean(c.n)}><strong>{clean(c.n)}</strong><span className="party-caption">{partyLabel(c.p)}</span></span>
              <span className="candidate-total">{r.reported && typeof c.pct==="number" && Number.isFinite(c.pct) && c.pct>=0&&c.pct<=100?c.pct.toFixed(1)+"%":r.reported?nfmt(c.v):"—"}</span>
            </div>)}
          </div> : <p className="empty-candidates">Candidate breakdown not yet published by this results source.</p>}
          {r.candidates.length>3&&<span className="party-caption">+ {r.candidates.length-3} additional candidate(s) · see race explorer</span>}
          {r.roster&&(!r.race||r.webSourceUrl)&&<a className="roster-source" target="_blank" rel="noreferrer" href={r.roster.sourceUrl}>{r.roster.kind==="filing"?"FEC registrations (not verified ballot)":"Official candidate list"} · {r.roster.authority}{r.webUpdated?" · "+r.webUpdated:""}</a>}
          <div className="race-card-foot"><span>{r.reported?nfmt(r.race?.total)+" votes":"No reported votes"}</span><span>{typeof r.race?.pct_in==="number"&&r.race.pct_in>=0&&r.race.pct_in<=100?r.race.pct_in+"% precincts":"Precincts —"}</span></div>
        </article>):<div className="no-races">No races match these filters. Choose another chamber or state.</div>}
      </div>
      {year===2026&&!dataPublished&&<div className="historical-link"><span>Want to see actual candidate names and vote percentages now? Explore verified historical results.</span><button type="button" onClick={()=>{setYear(2024);setState("All");setSearch("")}}>Explore 2024 results</button></div>}
      <div className="map-panel"><div className="sectionheading"><div><h2>{mapMode==="coverage"?"U.S. results coverage map":mapMode==="senate-called"?"Source-called Senate winners":"Reported Senate vote leaders by state"}</h2><p>{mapMode==="coverage"?"Interactive map · colors show source availability, not party control":mapMode==="senate-called"?"Solid colors show verified source-called Senate winners only. Neutral states have no linked call; not certification.":"Colors identify the party of the candidate currently leading reported Senate votes. Not a seat call, forecast or statewide House result."}</p></div><span>{mapMode==="coverage"?states.filter(code=>mapCounts[code]?.reported>0).length+" states with reported contests":mapMode==="senate-called"?Object.keys(senateWinners).length+" states with a sourced Senate call":senateStatesReporting+" states with published Senate leaders"}</span></div>
        <div className="map-mode" role="group" aria-label="Choose map data layer">
          <button type="button" aria-pressed={mapMode==="coverage"} className={mapMode==="coverage"?"selected":""} onClick={()=>setMapMode("coverage")}>Source coverage</button>
          <button type="button" aria-pressed={mapMode==="senate-leaders"} className={mapMode==="senate-leaders"?"selected":""} onClick={()=>setMapMode("senate-leaders")}>Senate vote leader party</button>
          <button type="button" aria-pressed={mapMode==="senate-called"} className={mapMode==="senate-called"?"selected":""} onClick={()=>setMapMode("senate-called")}>Senate called winners</button>
        </div>
        <UsMap counts={mapCounts} selected={state} onSelect={setState} mode={mapMode} senateLeaders={senateLeadByState} senateWinners={senateWinners}/>
        {mapMode==="senate-called"?<div className="map-legend"><span><i className="legend-swatch" style={{backgroundColor:"#2563eb"}}/> Democratic called</span><span><i className="legend-swatch" style={{backgroundColor:"#c82b42"}}/> Republican called</span><span><i className="legend-swatch" style={{backgroundColor:"#dbe5f2"}}/> Not yet sourced</span><button type="button" onClick={()=>setState("All")}>Clear state filter</button></div>:mapMode==="coverage"?<div className="map-legend"><span><i className="legend-swatch tile-reported"/> Votes reported</span><span><i className="legend-swatch tile-listed"/> Candidate/source listing, no votes</span><span><i className="legend-swatch tile-pending"/> No results available</span><button type="button" onClick={()=>setState("All")}>Clear state filter</button></div>:
        <div className="map-legend"><span><i className="legend-swatch" style={{backgroundColor:"#2563eb"}}/> Democrat currently leading</span><span><i className="legend-swatch" style={{backgroundColor:"#c82b42"}}/> Republican currently leading</span><span><i className="legend-swatch" style={{backgroundColor:"#7251b5"}}/> Independent currently leading</span><span><i className="legend-swatch" style={{backgroundColor:"#dbe5f2"}}/> No substantiated Senate vote leader</span><button type="button" onClick={()=>setState("All")}>Clear state filter</button></div>}
        {mapMode==="senate-leaders"&&<p className="muted">Senate colors use only published candidate vote counts; missing states remain neutral. House contests are tracked separately by district in the race explorer.</p>}
        {mapMode==="senate-called"&&<p className="muted">Known named calls from attributed news reports or independent decision desks, not certified results. The colored states are a partial verified subset, not complete nationwide AP map coverage.</p>}
      </div>
    </section>
    <section className="results"><div className="sectionheading"><div><h2>Race explorer</h2><p>Filter by House, Senate, governor, state, district, or candidate.</p></div><span>{filtered.length} contests</span></div><div className="filters"><label>Chamber<select value={office} onChange={e=>setOffice(e.target.value as "Both"|Office)}><option>Both</option><option>House</option><option>Senate</option><option>Governor</option></select></label><label>State<select value={state} onChange={e=>setState(e.target.value)}><option>All</option>{states.map(s=><option key={s}>{s}</option>)}</select></label><label>Search<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="e.g. TX-23 or candidate" /></label></div><div className="tablewrap"><table><thead><tr><th>Contest</th><th>Chamber</th><th>State</th><th>Coverage</th><th>Votes</th><th>Leading / source-called</th><th>Margin</th><th>Precincts</th></tr></thead><tbody>{filtered.slice(0,250).map(r=><tr key={r.office+r.key}><td><strong>{r.key}</strong>{r.candidates.length>0&&<details><summary>{r.candidates.length} candidates</summary>{r.candidates.map((c,i)=><div className="candidate-details" key={i}><span className={"party-badge "+partyClass(c.p)} title={partyLabel(c.p)}>{partyCode(c.p)}</span><span>{clean(c.n)} <span className="party-caption">({partyLabel(c.p)})</span></span><span className="candidate-votes">{nfmt(c.v)} votes</span></div>)}</details>}</td><td>{r.office}</td><td>{r.state}</td><td>{r.reported?"Votes reported":r.race?"Listed, no votes":r.roster?(r.roster.kind==="filing"?"FEC filing; ballot unverified":"Official candidates; votes pending"):r.feed?(supportedResultsStates.has(r.state)?"Awaiting state returns":"No automatic results feed"):"Results source unavailable"}</td><td>{nfmt(r.race?.total)}</td><td>{r.insight.sourceCalledWinner?"Source called: "+clean(r.insight.sourceCalledWinner):r.insight.leader?clean(r.insight.leader.n)+" ("+partyLabel(r.insight.leader.p)+")":"—"}</td><td>{r.insight.voteMargin!==null?nfmt(r.insight.voteMargin)+" votes"+(r.insight.marginPct!==null?" / "+r.insight.marginPct.toFixed(2)+"%":""):"—"}</td><td>{typeof r.race?.pct_in==="number"&&r.race.pct_in>=0&&r.race.pct_in<=100?r.race.pct_in+"%":"—"}</td></tr>)}</tbody></table></div>{filtered.length>250&&<p className="muted">Showing the first 250 matching contests. Narrow the state or search to see other races.</p>}</section></>}
    {country==="US"&&year===2026&&closeAlert&&closeContests.length>0&&<aside className="close-alert" role="dialog" aria-modal="false" aria-label="Close election alerts">
      <div className="close-header"><h3>Close reported contests · {closeContests.length}</h3><button type="button" aria-label="Dismiss close race alert" onClick={()=>setCloseAlert(false)}>✕</button></div>
      <p>Vote margins are calculated from published counts. These are not predictions or final outcomes.</p>
      {closeContests.slice(0,4).map(r=><div className="alert-row" key={r.office+r.key}><button type="button" onClick={()=>chooseRace(r)}>{r.state} · {r.office} {r.key}</button><span> — {r.insight.marginPct?.toFixed(2)}% · {nfmt(r.insight.voteMargin)}-vote margin</span></div>)}
    </aside>}
    <footer>Independent election information viewer · <a href="https://civicpulse-2026.streamlit.app" target="_blank" rel="noreferrer">Original Streamlit dashboard</a> · Source publication is not independent certification.</footer>
  </main>;
}
