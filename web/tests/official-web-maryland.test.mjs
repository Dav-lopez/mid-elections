import test from "node:test";
import assert from "node:assert/strict";
import { parseMarylandHouse, marylandHouseUrl } from "../lib/official-web-maryland.ts";

const table=(votes="NR",total="NR",precincts=0)=>`
<html><body>
  <h1>Unofficial 2026 Gubernatorial General Election Results for Representative in Congress</h1>
  <p>Last refreshed: 11/02/2026 04:39:30 PM</p>
  <h3>District 1</h3>
  <p>(${precincts} of 309 election day precincts reported)</p>
  <p>Winner Selected: Denotes Winner of the Election</p>
  <table><thead><tr>
    <th>Name</th><th>Party</th><th>Early Voting</th><th>Election Day</th>
    <th>Mail-In Ballot</th><th>Provisional</th><th>Total</th><th>Percentage</th>
  </tr></thead><tbody>
    <tr><td>Dan Schwartz</td><td>Democratic</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>${votes}</td><td>52.1%</td></tr>
    <tr><td>Andy Harris</td><td>Republican</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>${votes==="NR"?"NR":"230"}</td><td>47.9%</td></tr>
    <tr><td>Edward Shlikas (Write-In)</td><td>Unaffiliated</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td></tr>
    <tr><td>Other Write-Ins</td><td></td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>NR</td></tr>
    <tr><td>Totals</td><td></td><td>NR</td><td>NR</td><td>NR</td><td>NR</td><td>${total}</td><td>100%</td></tr>
  </tbody></table>
</body></html>`;

test("Maryland official results pages expose candidate and party data before voting returns",()=>{
  const data=parseMarylandHouse(table(),1);
  assert.equal(data.seat,"MD-01");
  assert.equal(data.cands.length,3);
  assert.deepEqual(data.cands.map(c=>[c.n,c.p,c.v]),[
    ["Dan Schwartz","D",null],["Andy Harris","R",null],
    ["Edward Shlikas (Write-In)","I",null]
  ]);
  assert.equal(data.total,null);
  assert.equal(data.pct_in,null);
  assert.equal(data.called,false);
  assert.equal(data.winner,"");
  assert.equal(data.updatedLabel,"11/02/2026 04:39:30 PM Eastern");
  assert.equal(data.sourceUrl,marylandHouseUrl(1));
});

test("Maryland website total is used only when explicitly published, never summed",()=>{
  const data=parseMarylandHouse(table("250","500",124),1);
  assert.equal(data.cands[0].v,250);
  assert.equal(data.cands[1].v,230);
  assert.equal(data.total,500);
  assert.equal(data.pct_in,40.13);
  assert.equal(data.called,false);
});

test("missing official total does not become the sum of candidate votes",()=>{
  const data=parseMarylandHouse(table("250","NR",124),1);
  assert.equal(data.total,null);
});

test("generic winner icon/legend does not constitute a source race call",()=>{
  const data=parseMarylandHouse(table("250","500",124),1);
  assert.equal(data.called,false);
  assert.equal(data.winner,"");
});

test("unexpected district, election, or absent table is rejected",()=>{
  assert.throws(()=>parseMarylandHouse(table(),2),/identity mismatch/i);
  assert.throws(()=>parseMarylandHouse(table().replace("2026","2024"),1),/identity mismatch/i);
  assert.throws(()=>parseMarylandHouse(table().replace(/<table>[\s\S]*<\/table>/,""),1),/table not found/i);
});
