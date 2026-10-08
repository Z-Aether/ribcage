// The #10 model as a MILP in CPLEX LP format, solved with HiGHS (highs-js WASM).
//   max  K*W*m + K*sum_i sum_f s[i][f]*y[i][f] + sum_f c[f]*x[f]
//   s.t. sum_f y[i][f] <= 1        (each voter has at most one representative)
//        y[i][f] <= x[f]           (representative must be in the slate)
//        m <= sum_f s[i][f]*y[i][f](the protected floor)
//        sum_f r[f]*x[f] <= B      (the time budget - the only hard constraint)
// y is only created for eligible (i,f) pairs: not seen, not vetoed.
// K=4001 > 2*max|T| so the total term can only ever break ties.
const {makeInstance} = require('./instance.js');
const K = 4001;

function buildLP(inst, B, nogoods = []){
  const {F, V, r, s, elig, c} = inst;
  const W = V;
  const obj = [], rows = [], bins = ['m_int'];
  obj.push(`+ ${K*W} m_int`);
  for (let f=0; f<F; f++){ if (c[f] !== 0) obj.push(`${c[f] >= 0 ? '+' : '-'} ${Math.abs(c[f])} x_${f}`); }
  const yv = [];
  for (let i=0; i<V; i++){
    const mine = [];
    for (let f=0; f<F; f++){
      if (!elig[i][f]) continue;
      const name = `y_${i}_${f}`; mine.push({name, f, s: s[i][f]}); yv.push(name);
      if (s[i][f] !== 0) obj.push(`${s[i][f] >= 0 ? '+' : '-'} ${Math.abs(K*s[i][f])} ${name}`);
      rows.push(`link_${i}_${f}: ${name} - x_${f} <= 0`);
    }
    rows.push(`one_${i}: ${mine.map(o=>`+ ${o.name}`).join(' ')} <= 1`);
    const repTerms = mine.filter(o=>o.s!==0).map(o=>`${o.s>=0?'-':'+'} ${Math.abs(o.s)} ${o.name}`).join(' ');
    rows.push(`floor_${i}: + m_int ${repTerms} <= 0`);
  }
  rows.push(`budget: ${[...Array(F).keys()].map(f=>`+ ${r[f]} x_${f}`).join(' ')} <= ${B}`);
  // A minimum-Hamming-distance cut against each previously found slate S:
  //   sum_{f in S} (1 - x_f) + sum_{f not in S} x_f >= k
  nogoods.forEach((S, n) => {
    const set = new Set(S);
    const lhs = [...Array(F).keys()].map(f => set.has(f) ? `- x_${f}` : `+ x_${f}`).join(' ');
    rows.push(`diverse_${n}: ${lhs} >= ${nogoods.k || 2} - ${S.length}`);
  });
  return [
    'Maximize', ' obj: ' + obj.join(' '),
    'Subject To', ...rows.map(r=>' '+r),
    'Bounds', ' 0 <= m_int <= 3',
    'Binaries', ' ' + [...Array(F).keys()].map(f=>`x_${f}`).join(' ') + ' ' + yv.join(' '),
    'End'
  ].join('\n');
}

async function main(){
  const highs = await require('highs')();
  const F = Number(process.env.F || 50), V = Number(process.env.V || 10);
  const budgets = process.env.B ? [Number(process.env.B)] : [360, 480, 600, 720, 840, 960, 1080, 1440, 2880];
  console.log('| films | voters | budget | LP rows | LP cols | status | solve time | objective | slate size |');
  console.log('|---|---|---|---|---|---|---|---|---|');
  for (const B of budgets){
    const inst = makeInstance({F, V, seed: 7});
    const lp = buildLP(inst, B);
    const t0 = process.hrtime.bigint();
    const res = highs.solve(lp);
    const ms = Number(process.hrtime.bigint()-t0)/1e6;
    const chosen = Object.entries(res.Columns).filter(([n,v])=>n.startsWith('x_') && v.Primal > 0.5).map(([n])=>Number(n.slice(2)));
    const rows = Object.keys(res.Rows||{}).length, cols = Object.keys(res.Columns).length;
    console.log(`| ${F} | ${V} | ${B} min (${(B/60).toFixed(0)}h) | ${rows} | ${cols} | ${res.Status} | **${ms.toFixed(0)} ms** | ${res.ObjectiveValue} | ${chosen.length} |`);
  }
}
module.exports={buildLP,K};
if (require.main===module) main().catch(e=>{console.error(e); process.exit(1)});
