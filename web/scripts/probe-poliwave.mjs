import {load} from "cheerio";
try{
 const response=await fetch("https://www.poliwave.com/us/live/midterms-2026",{signal:AbortSignal.timeout(13000),headers:{Accept:"text/html"}});
 const html=await response.text();
 console.log("POLIWAVE HTTP",response.status,"BYTES",html.length);
 if(!response.ok)process.exit(0);
 const t=load(html)("body").text().replace(/\s+/g," ").trim();
 for(const phrase of ["Balance of power","Key races","Close races"]){
   const at=t.indexOf(phrase);
   console.log("POLIWAVE",phrase,at,t.slice(at,at+1200));
 }
}catch(e){console.log("POLIWAVE UNAVAILABLE",String(e).slice(0,400));}
