// k-best with diversity, for #17: solve, add a minimum-Hamming-distance cut
// against every slate found so far, re-solve. Measures cost and quality decay.
const {makeInstance} = require('./instance.js');
const {buildLP, K} = require('./mip.js');

function withDiversity(lpText, prev, F, minDiff){
  if (!prev.length) return lpText;
  const cuts = prev.map((S, n) => {
    const set = new Set(S);
    const lhs = [...Array(F).keys()].map(f => set.has(f) ? `- x_${f}` : `+ x_${f}`).join(' ');
    return ` diverse_${n}: ${lhs} >= ${minDiff - S.length}`;
  });
  return lpText.replace('\nBounds', '\n' + cuts.join('\n') + '\nBounds');
}

(async () => {
  const highs = await require('highs')();
  highs.solve('Maximize\n obj: x\nSubject To\n c: x <= 1\nBounds\n 0 <= x <= 1\nEnd');
  const OPTS = {mip_rel_gap: 0, mip_abs_gap: 0};
  for (const minDiff of [1, 2, 3]){
    console.log(`\n### minimum set-difference = ${minDiff} film(s), budget 720 min, 50 films, 10 voters\n`);
    console.log('| proposal | objective | loss vs optimum | floor m | slate size | solve time |');
    console.log('|---|---|---|---|---|---|');
    const inst = makeInstance({seed: 7});
    const base = buildLP(inst, 720);
    const prev = []; let opt = null, total = 0;
    for (let n = 0; n < 5; n++){
      const t0 = process.hrtime.bigint();
      const res = highs.solve(withDiversity(base, prev, inst.F, minDiff), OPTS);
      const ms = Number(process.hrtime.bigint()-t0)/1e6; total += ms;
      if (res.Status !== 'Optimal'){ console.log(`| ${n+1} | — | — | — | — | ${res.Status} |`); break; }
      const objv = Math.round(res.ObjectiveValue);
      if (opt === null) opt = objv;
      const S = Object.entries(res.Columns).filter(([k,v])=>k.startsWith('x_') && v.Primal>0.5).map(([k])=>Number(k.slice(2)));
      const m = Math.round(res.Columns.m_int.Primal);
      console.log(`| ${n+1} | ${objv} | ${opt-objv} | ${m} | ${S.length} | ${ms.toFixed(0)} ms |`);
      prev.push(S);
    }
    console.log(`\nTotal for 5 proposals: **${total.toFixed(0)} ms**`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
