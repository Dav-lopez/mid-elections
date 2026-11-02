"use client";
import { useEffect, useMemo, useState } from "react";
import "./dashboard.css";

type Candidate = { n?: string; p?: string; v?: number | null; pct?: number | null };
type Race = { cands?: Candidate[]; total?: number | null; pct_in?: number | null; leader?: string | null; winner?: string | null; called?: boolean };
type Feed = { api: number; year: number; office: string; live: boolean; stale: boolean; counting: boolean; final: boolean; as_of: string | null; source: string; races: Record<string, Race> };
type Office = "House" | "Senate";
const API = "https://openamerica.io/elections/results.json";
const states = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
const house: Record<string,number> = {AL:7,AK:1,AZ:9,AR:4,CA:52,CO:8,CT:5,DE:1,FL:28,GA:14,HI:2,ID:2,IL:17,IN:9,IA:4,KS:4,KY:6,LA:6,ME:2,MD:8,MA:9,MI:13,MN:8,MS:4,MO:8,MT:2,NE:3,NV:4,NH:2,NJ:12,NM:3,NY:26,NC:14,ND:1,OH:15,OK:5,OR:6,PA:17,RI:2,SC:7,SD:1,TN:9,TX:38,UT:4,VT:1,VA:11,WA:10,WV:2,WI:8,WY:1};
const senate = "AL AK AR CO DE GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OK OR RI SC SD TN TX VA WV WY".split(" ");
const seats = [...Object.entries(house).flatMap(([state,n])=>Array.from({length:n},(_,i)=>({office:"House" as Office,state,key:state+"-"+(n===1?"00":String(i+1).padStart(2,"0"))}))),...senate.map(state=>({office:"Senate" as Office,state,key:state})),...["FL","OH"].map(state=>({office:"Senate" as Office,state,key:state+"-SPECIAL"}))];
const validVotes=(x:unknown):x is number=>typeof x==="number"&&Number.isSafeInteger(x)&&x>=0;
const nfmt=(x:unknown)=>validVotes(x)?x.toLocaleString("en-US"):"Not reported";
const clean=(s:unknown)=>typeof s==="string"?s.slice(0,120):"";
const baseUrl=(year:number,office:Office)=>API+"?year="+year+"&office="+office;
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
  useEffect(()=>{
    if(country!=="US"){setFeeds({});setErrors({});return;}
    let cancelled=false;
    const get=async()=>{
      setBusy(true);
      const results=await Promise.all((["House","Senate"] as Office[]).map(async o=>{
        try {
          const response=await fetch(baseUrl(year,o),{cache:"no-store",headers:{"Accept":"application/json"}});
          if(!response.ok)throw new Error("HTTP "+response.status);
          const data:unknown=await response.json();
          if(!data||typeof data!=="object")throw new Error("Invalid feed");
          const f=data as Feed;
          if(f.api!==1||f.year!==year||f.office.toLowerCase()!==o.toLowerCase()||typeof f.races!=="object"||f.races===null||Array.isArray(f.races)||typeof f.live!=="boolean"||typeof f.stale!=="boolean"||typeof f.counting!=="boolean"||typeof f.final!=="boolean")throw new Error("Feed failed metadata validation");
          return {office:o,feed:f,error:null};
        }catch(e){return {office:o,feed:null,error:e instanceof Error?e.message:"Request failed"};}
      }));
      if(cancelled)return;
      setFeeds(prev=>{const next={...prev};for(const r of results){if(r.feed)next[r.office]=r.feed;else if(prev[r.office]?.year!==year)delete next[r.office];}return next;});
      setErrors(Object.fromEntries(results.filter(r=>r.error).map(r=>[r.office,r.error])) as Partial<Record<Office,string>>);
      setChecked(new Date().toISOString());
      setBusy(false);
    };
    void get();
    const timer=setInterval(()=>setRefresh(v=>v+1),feeds.House?.live||feeds.Senate?.live?60000:600000);
    return ()=>{cancelled=true;clearInterval(timer);};
    // The timer resets with the live status; each cycle cleans up the previous timer.
  },[year,country,refresh,feeds.House?.live,feeds.Senate?.live]);
  const rows=useMemo(()=>{
    if(country!=="US")return [];
    const registry=year===2026?seats:[...new Set([...Object.values(feeds).flatMap(f=>f&&f.year===year?Object.entries(f.races).map(([key])=>({office:f.office as Office,state:key.slice(0,2),key})):[])])];
    return registry.map(s=>{const f=feeds[s.office]?.year===year?feeds[s.office]:undefined;const race=f?.races?.[s.key]??null;const candidates=Array.isArray(race?.cands)?race.cands.filter(c=>c&&typeof c.n==="string"):[];const reported=validVotes(race?.total)&&race.total>0||candidates.some(c=>validVotes(c.v)&&c.v>0);return {...s,race,candidates,reported,feed:f};});
  },[country,year,feeds]);
  const filtered=rows.filter(r=>(office==="Both"||r.office===office)&&(state==="All"||r.state===state)&&(!search||r.key.toLowerCase().includes(search.toLowerCase())||r.candidates.some(c=>clean(c.n).toLowerCase().includes(search.toLowerCase()))));
  const listed=rows.filter(r=>r.race).length,reported=rows.filter(r=>r.reported).length;
  const live=Object.values(feeds).some(f=>f?.year===year&&f.live);
  return <main className="dashboard">
    <header className="hero"><div className="eyebrow">CIVICPULSE · SOURCE-AWARE ELECTION INFORMATION</div><h1>Election Results Dashboard</h1><p>Official-source reporting where available. No forecasts, invented totals, or inferred winners.</p><div className="topline"><span>{country==="US"?"United States":"Nigeria"}</span><span>{country==="US"?year:2027} election coverage</span><span>{live?"● Live counting":"● Not live"}</span></div></header>
    <div className="controls"><label>Country<select value={country} onChange={e=>{setCountry(e.target.value as "US"|"NG");setState("All")}}><option value="US">United States</option><option value="NG">Nigeria</option></select></label><label>Election<select value={country==="US"?year:2027} disabled={country==="NG"} onChange={e=>setYear(Number(e.target.value))}><option value={2026}>2026 Congressional</option><option value={2024}>2024 Historical replay</option></select></label><button onClick={()=>setRefresh(v=>v+1)} disabled={busy||country!=="US"}>{busy?"Checking source…":"Refresh source"}</button></div>
    {country==="NG"?<section className="notice"><h2>Nigeria 2027 · Integration pending</h2><p>INEC-backed election feeds and validated candidate rosters are not connected yet. No Nigerian vote totals are displayed.</p></section>:<>
    <section className="metrics"><article><span>Tracked contests</span><strong>{rows.length.toLocaleString()}</strong></article><article><span>Listed by provider</span><strong>{listed.toLocaleString()}</strong></article><article><span>Contests with votes</span><strong>{reported.toLocaleString()}</strong></article><article><span>Feed status</span><strong>{live?"Live":Object.values(feeds).some(f=>f?.stale)?"Stale":"Not live"}</strong></article></section>
    <section className="notice"><strong>{year===2024?"Historical 2024 vote totals — not 2026 results.":"2026 general election · November 3, 2026"}</strong><p>Counts are displayed only when published by the source. Missing results are not zero. Precinct completion does not mean certification. A vote leader is not necessarily a winner.</p><p>Source: <a href="https://openamerica.io/elections/api/" target="_blank" rel="noreferrer">Open America election API, relaying state election-office counts</a>. Publisher timestamp: {Object.values(feeds).filter(f=>f?.year===year&&f.as_of).map(f=>f?.office+": "+new Date(f!.as_of!).toLocaleString()).join(" · ")||"Not published"}. Last checked: {checked?new Date(checked).toLocaleString():"Not checked"}.</p>{Object.entries(errors).map(([o,error])=><p className="warning" key={o}>{o}: source unavailable ({error}). Previously retrieved data may be stale.</p>)}</section>
    <section className="results"><div className="sectionheading"><div><h2>Race explorer</h2><p>Filter by chamber, state, district, or candidate.</p></div><span>{filtered.length} contests</span></div><div className="filters"><label>Chamber<select value={office} onChange={e=>setOffice(e.target.value as "Both"|Office)}><option>Both</option><option>House</option><option>Senate</option></select></label><label>State<select value={state} onChange={e=>setState(e.target.value)}><option>All</option>{states.map(s=><option key={s}>{s}</option>)}</select></label><label>Search<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="e.g. TX-23 or candidate" /></label></div><div className="tablewrap"><table><thead><tr><th>Contest</th><th>Chamber</th><th>State</th><th>Coverage</th><th>Votes</th><th>Source leader</th><th>Precincts</th></tr></thead><tbody>{filtered.slice(0,250).map(r=><tr key={r.office+r.key}><td><strong>{r.key}</strong>{r.candidates.length>0&&<details><summary>{r.candidates.length} candidates</summary>{r.candidates.map((c,i)=><div className="candidate" key={i}>{clean(c.n)} · {clean(c.p)||"Party not listed"} · {nfmt(c.v)} votes</div>)}</details>}</td><td>{r.office}</td><td>{r.state}</td><td>{r.reported?"Votes reported":r.race?"Listed, no votes":r.feed?"Not in feed":"Source unavailable"}</td><td>{nfmt(r.race?.total)}</td><td>{r.reported?clean(r.race?.leader)||"—":"—"}</td><td>{typeof r.race?.pct_in==="number"&&r.race.pct_in>=0&&r.race.pct_in<=100?r.race.pct_in+"%":"—"}</td></tr>)}</tbody></table></div>{filtered.length>250&&<p className="muted">Showing the first 250 matching contests. Narrow the state or search to see other races.</p>}</section></>}
    <footer>Independent election information viewer · <a href="https://civicpulse-2026.streamlit.app" target="_blank" rel="noreferrer">Original Streamlit dashboard</a> · Source publication is not independent certification.</footer>
  </main>;
}
