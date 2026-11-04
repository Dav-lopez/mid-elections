import test from "node:test";
import assert from "node:assert/strict";
import { parseRollCall } from "../lib/newsroom-calls.ts";

const fixture = `<html><body><article>
<h1>Key midterm election results</h1>
<p>CQ Roll Call is tracking the results in these battleground races, as they are called by The Associated Press.</p>
<p>Last updated at 9:02 p.m. Eastern time</p>
<ul>
<li>Georgia Senate: Democratic Sen. Jon Ossoff defeats Republican Rep. Mike Collins [Democratic hold]</li>
<li>North Carolina Senate (open): Democratic former Gov. Roy Cooper defeats Republican Michael Whatley [Democratic flip]</li>
<li>New Hampshire Senate: Democratic Rep. Chris Pappas defeats Republican John E. Sununu [Democratic hold]</li>
<li>Florida Senate: GOP Sen. Ashley Moody defeats Democratic Angie Nixon [Republican hold]</li>
<li>Florida’s 25th District: Democratic Rep. Jared Moskowitz defeats Republican Scott Singer [Democratic hold]</li>
<li>North Carolina’s 11th District (open): Democrat Jamie Ager defeats Republican Jennifer Balkcom [Democratic flip]</li>
<li>Florida Governor: Byron Donalds leads another candidate with 51% of reported votes [Republican hold]</li>
<li>Ohio Governor: Amy Acton is projected to lead with 59 percent [Democratic flip]</li>
</ul>
</article></body></html>`;

test("extract calls, parties, districts and publication time from named AP-attributed results", () => {
  const parsed = parseRollCall(fixture);
  assert.equal(parsed.calls.length, 6);
  assert.equal(parsed.updated, "November 3, 2026 · 9:02 p.m. Eastern time");
  const pick = (state,office) => parsed.calls.find(c=>c.state===state&&c.office===office);
  assert.equal(pick("Georgia","Senate").winner,"Jon Ossoff");
  assert.equal(pick("North Carolina","Senate").winner,"Roy Cooper");
  assert.equal(pick("Florida","Senate").winner,"Ashley Moody");
  assert.equal(pick("Florida","Senate").party,"R");
  assert.equal(pick("Florida","House").district,"25");
  assert.equal(pick("Florida","House").winner,"Jared Moskowitz");
  assert.equal(pick("North Carolina","House").district,"11");
  assert.equal(pick("North Carolina","House").winner,"Jamie Ager");
  assert.equal(parsed.calls.some(c=>c.office==="Governor"),false);
});

test("reject unattributed pages and pages with only forecasts or vote leads",()=>{
  assert.throws(()=>parseRollCall("<body>Key midterm election results</body>"),/attribution/);
  assert.throws(()=>parseRollCall(fixture.replaceAll("defeats","leads")),/No explicit race calls/);
});
