const urls=[
"https://civicapi.org/api/v2/race/search?country=US&startDate=2026-11-03&endDate=2026-11-03&query=Senate&limit=3",
"https://civicapi.org/api/v2/race/search?country=US&startDate=2026-11-03&endDate=2026-11-03&query=Governor&limit=3"
];
for(const url of urls){
 try{
  const response=await fetch(url,{signal:AbortSignal.timeout(12000)});
  const raw=await response.text();
  console.log("PROBE",url.replace("https://civicapi.org",""),"HTTP",response.status, "bytes",raw.length);
  const parsed=JSON.parse(raw);
  console.log("ROOT KEYS",Array.isArray(parsed)?"ARRAY":Object.keys(parsed).slice(0,20));
  const array=Array.isArray(parsed)?parsed:[parsed.races,parsed.results,parsed.data,parsed.items].find(Array.isArray);
  console.log("ITEMS",Array.isArray(array)?array.length:"not-array");
  console.log("SAMPLE",JSON.stringify(Array.isArray(array)?array[0]:parsed).slice(0,3200));
 }catch(e){console.log("PROBE UNAVAILABLE",String(e).slice(0,300));}
}
