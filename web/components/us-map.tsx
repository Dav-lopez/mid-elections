"use client";

import { geoAlbersUsa, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { FeatureCollection } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import usAtlas from "us-atlas/states-10m.json";

type Counts = {reported:number;listed:number;tracked:number};
type SenateLeader = { name:string;party:string;seat:string;votes:number };
type Props = { counts:Record<string,Counts>;selected:string;onSelect:(code:string)=>void;mode?:"coverage"|"senate-leaders";senateLeaders?:Record<string,SenateLeader> };
const PARTY_MAP_FILLS:Record<string,string>={D:"#2563eb",R:"#c82b42",I:"#7251b5",L:"#a9690b",G:"#128354"};

const byFips:Record<string,string> = {
  "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE",
  "12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS",
  "21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS",
  "29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY",
  "37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC",
  "46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV",
  "55":"WI","56":"WY"
};
const topology=usAtlas as unknown as Topology;
const geometries=topology.objects.states as GeometryCollection;
const mapFeatures=feature(topology,geometries) as FeatureCollection;
const projection=geoAlbersUsa().fitSize([960,550],mapFeatures);
const path=geoPath(projection);

export default function UsMap({counts,selected,onSelect,mode="coverage",senateLeaders={}}:Props){
  return <svg className="us-choropleth" viewBox="0 0 960 550" role="group" aria-label="Map of 50 U.S. states. Select a state to filter election contests">
    {mapFeatures.features.map(shape=>{
      const code=byFips[String(shape.id).padStart(2,"0")];
      if(!code)return null;
      const data=counts[code]??{reported:0,listed:0,tracked:0};
      const stateClass=data.reported>0?"tile-reported":data.listed>0?"tile-listed":"tile-pending";
      // Explicit SVG fill: CSS background-color alone does not color <path> elements.
      const senateLeader=senateLeaders[code];
      const fill=mode==="senate-leaders"
        ? (senateLeader ? PARTY_MAP_FILLS[senateLeader.party]??"#7893ad" : "#dbe5f2")
        : (data.reported>0?"#087e83":data.listed>0?"#f2b94b":"#dbe5f2");
      const description=mode==="senate-leaders"
        ? senateLeader
          ? code+": "+senateLeader.name+" ("+senateLeader.party+") leads currently published Senate votes for "+senateLeader.seat+"; not a final result"
          : code+": no published Senate vote leader for display (not a forecast)"
        : code+": "+data.reported+" contests with votes, "+data.listed+" contests listed in results or official candidate sources";
      const handleSelect=()=>onSelect(selected===code?"All":code);
      return <path key={code} d={path(shape)||""} className={"state-shape "+stateClass+(selected===code?" shape-selected":"")} fill={fill} style={{fill}}
        role="button" tabIndex={0} aria-label={description} aria-pressed={selected===code} onClick={handleSelect}
        onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();handleSelect();}}}>
        <title>{description}</title>
      </path>;
    })}
  </svg>;
}
