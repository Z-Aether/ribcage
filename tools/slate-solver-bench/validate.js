// Cross-check: does the HiGHS MILP optimum equal the exhaustive-enumeration
// optimum? Run on every budget where exhaustive enumeration finishes.
const {makeInstance} = require('./instance.js');
const {enumerate} = require('./enumerate.js');
const path = require('path');

const {buildLP} = require('./mip.js');

(async () => {
  const highs = await require('highs')();
  highs.solve('Maximize\n obj: x\nSubject To\n c: x <= 1\nBounds\n 0 <= x <= 1\nEnd'); // warm up WASM
  console.log('| seed | budget | enumerated optimum | MILP optimum | agree? | enum time | MILP time |');
  console.log('|---|---|---|---|---|---|---|');
  let allAgree = true;
  for (const seed of [1,2,3,7,11]){
    for (const B of [360, 480, 600, 720]){
      const inst = makeInstance({seed});
      const e = enumerate(inst, B, {timeLimitMs: 120000});
      const t0 = process.hrtime.bigint();
      const res = highs.solve(buildLP(inst, B), {mip_rel_gap: 0, mip_abs_gap: 0});
      const ms = Number(process.hrtime.bigint()-t0)/1e6;
      const mObj = Math.round(res.ObjectiveValue);
      const agree = !e.timedOut && mObj === e.best;
      if (!agree) allAgree = false;
      console.log(`| ${seed} | ${B} | ${e.best} | ${mObj} | ${agree?'yes':'**NO**'} | ${e.ms} ms | ${ms.toFixed(0)} ms |`);
    }
  }
  console.log('\nall agree:', allAgree);
})().catch(e=>{console.error(e);process.exit(1)});
