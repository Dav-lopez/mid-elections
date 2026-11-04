import test from "node:test";
import assert from "node:assert/strict";
import {parseElectionNightPage} from "../lib/election-night.ts";

const sample=`<main><h1>2026 midterm election results: live Senate, House and governor races</h1>
<div>Updated November 3, 2026 at 11:02 PM EST</div>
<section>Balance of power
 House 435 seats up · 195 called Democrats 116+74 leading Republicans 79+80 leading 218 for control
 Senate 35 of 100 seats up · 27 called Democrats 50 Republicans 40+4 leading Ind. 2 Other 0+1 51 for control
 Governors 36 of 50 races up · 21 called Democrats 20+5 leading Republicans 15+4 leading
</section>
<h2>Control of Congress, live projection</h2>
<p>Forecast, never a call: Democrats 241 seats, Republicans 194</p>
<h2>Key races</h2><div>Texas Senate Dem. gain ✓James Talarico Democratic Party 59.5% 4,083,686</div>
<div>Ohio Governor Dem. gain ✓Amy Acton Democratic Party 50.8% 2,085,113</div>
<h2>Close races</h2><p>Counting Tennessee House District 7</p>
</main>`;
test("read called seat balance without accidentally reading forecast seats",()=>{
 const result=parseElectionNightPage(sample,"2026-11-04T04:02:00Z");
 assert.equal(result.offices.House.called,195);
 assert.equal(result.offices.House.dem,116);
 assert.equal(result.offices.House.rep,79);
 assert.equal(result.offices.House.demLeading,74);
 assert.equal(result.offices.Senate.dem,50);
 assert.equal(result.offices.Senate.independent,2);
 assert.equal(result.offices.Senate.rep,40);
 assert.equal(result.offices.Governor.called,21);
 assert.equal(result.offices.Governor.dem,20);
 assert.equal(result.source,"Poliwave");
 assert.equal(result.stale,false);
 assert.deepEqual(result.calls.map(x=>[x.state,x.office,x.winner,x.party]),[
  ["Texas","Senate","James Talarico","D"],["Ohio","Governor","Amy Acton","D"]
 ]);
});
test("reject malformed or stale-identity pages instead of fabricating results",()=>{
 assert.throws(()=>parseElectionNightPage("<body>2026 midterm election results</body>","x"),/Cannot distinguish/i);
 assert.throws(()=>parseElectionNightPage(sample.replace("195 called","999 called"),"x"),/constraints/);
 assert.throws(()=>parseElectionNightPage(sample.replace("Updated November 3, 2026 at 11:02 PM EST",""),"x"),/timestamp/);
});
