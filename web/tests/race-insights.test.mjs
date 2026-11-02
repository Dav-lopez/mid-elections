import test from "node:test";
import assert from "node:assert/strict";
import { partyCode, partyLabel, raceInsight, sourceCalledParty } from "../lib/race-insights.ts";

test("party names and abbreviations are displayed consistently", () => {
  assert.equal(partyCode("DEM"), "D");
  assert.equal(partyLabel("R"), "Republican");
  assert.equal(partyLabel("independent"), "Independent");
  assert.equal(partyCode(undefined), "—");
  assert.equal(partyLabel(undefined), "Party not listed");
});

test("no votes never produce a leader or a source-called seat", () => {
  assert.deepEqual(raceInsight({total:0, called:true, winner:"Sample Candidate", cands:[
    {n:"Sample Candidate",p:"D",v:0}, {n:"Other Candidate",p:"R",v:0}
  ]}), {
    leader:null, runnerUp:null, voteMargin:null, marginPct:null, close:false, sourceCalledWinner:null
  });
});

test("close races are derived only from published vote counts", () => {
  const insight=raceInsight({total:1000, cands:[
    {n:"Candidate A",p:"D",v:510},
    {n:"Candidate B",p:"R",v:490}
  ]});
  assert.equal(insight.leader?.n,"Candidate A");
  assert.equal(insight.voteMargin,20);
  assert.equal(insight.marginPct,2);
  assert.equal(insight.close,true);
  assert.equal(insight.sourceCalledWinner,null);
});

test("missing race-wide totals never manufacture a close percentage", () => {
  const insight=raceInsight({cands:[{n:"A",v:101},{n:"B",v:100}]});
  assert.equal(insight.leader?.n,"A");
  assert.equal(insight.voteMargin,1);
  assert.equal(insight.marginPct,null);
  assert.equal(insight.close,false);
});

test("a tie is not reported as a leader", () => {
  const insight=raceInsight({total:200,cands:[{n:"A",v:100},{n:"B",v:100}]});
  assert.equal(insight.leader,null);
  assert.equal(insight.close,false);
});

test("a source call is explicit and not certification", () => {
  const race={total:1000,cands:[{n:"A",v:510},{n:"B",v:490}],winner:"A"};
  assert.equal(raceInsight(race).sourceCalledWinner,null);
  const called=raceInsight({...race,called:true});
  assert.equal(called.sourceCalledWinner,"A");
  assert.equal(called.close,false);
});

test("an inconsistent total cannot yield a misleading margin percentage", () => {
  const insight=raceInsight({total:100,cands:[{n:"A",v:90},{n:"B",v:80}]});
  assert.equal(insight.marginPct,null);
  assert.equal(insight.close,false);
});

test("a publisher-called seat gets a party only with an exact reported candidate match", () => {
  const race={total:500,cands:[{n:"Candidate A",p:"DEM",v:300},{n:"Candidate B",p:"REP",v:200}],called:true,winner:"Candidate A"};
  assert.equal(sourceCalledParty(race),"D");
  assert.equal(sourceCalledParty({...race,winner:"Unlisted Name"}),null);
  assert.equal(sourceCalledParty({...race,called:false}),null);
  assert.equal(sourceCalledParty({...race,total:0,cands:[{n:"Candidate A",p:"D",v:0}]}),null);
});
