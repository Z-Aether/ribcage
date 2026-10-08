// The seed-7 / B=720 disagreement: enumeration says 240133, HiGHS says 240132.
// Hypothesis: HiGHS's default relative MIP gap (mip_rel_gap = 1e-4) is larger
// than the epsilon tie-break term, so it stops early and still reports "Optimal".
const {makeInstance} = require('./instance.js');
const path = require('path'), fs = require('fs');
const buildLP = new Function('require','module','exports','__dirname',
  fs.readFileSync(path.join(__dirname,'mip.js'),'utf8').replace(/^main\(\).*$/m,'') + '\nreturn buildLP;'
)(require,{},{},__dirname);

(async () => {
  const highs = await require('highs')();
  const inst = makeInstance({seed:7});
  const lp = buildLP(inst, 720);
  for (const opts of [{}, {mip_rel_gap: 0}, {mip_rel_gap: 0, mip_abs_gap: 0}]){
    const t0 = process.hrtime.bigint();
    const res = highs.solve(lp, opts);
    const ms = Number(process.hrtime.bigint()-t0)/1e6;
    console.log(`options ${JSON.stringify(opts).padEnd(38)} status=${res.Status} obj=${Math.round(res.ObjectiveValue)} (${ms.toFixed(0)} ms)`);
  }
  console.log('\nexhaustive enumeration optimum: 240133');
  console.log('default mip_rel_gap = 1e-4 -> tolerated absolute slack at this objective:', (240133*1e-4).toFixed(1));
})().catch(e=>{console.error(e);process.exit(1)});
