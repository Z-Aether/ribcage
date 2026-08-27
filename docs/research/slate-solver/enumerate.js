// Exhaustive enumeration of every budget-feasible slate, evaluating the #10
// objective  W*m + sum(rep) + eps*T  exactly.
// Integerised: obj = (W*m + sum(rep)) * K + T, with K > 2*max|T| so that T can
// only ever break ties. rep[i] in {0..3} because rep floors at 0 (see #10).
const {makeInstance} = require('./instance.js');

function enumerate(inst, B, {timeLimitMs=Infinity}={}){
  const {F, V, r, s, elig, c} = inst;
  // Sort films by runtime ascending so the "nothing else fits" prune bites early.
  const ord = [...Array(F).keys()].sort((a,b)=>r[a]-r[b]);
  const R = ord.map(f=>r[f]);
  const C = ord.map(f=>c[f]);
  const S = [], E = [];
  for (let i=0;i<V;i++){ S.push(ord.map(f=>s[i][f])); E.push(ord.map(f=>elig[i][f])); }
  // suffixMin[i] = smallest runtime among films i..F-1 (Infinity past the end)
  const suffixMin = new Int32Array(F+1).fill(0x7fffffff);
  for (let i=F-1;i>=0;i--) suffixMin[i] = Math.min(R[i], suffixMin[i+1]);

  const K = 4001;                       // |T| <= 3*V*F = 1500 for V=10,F=50
  const W = V;
  const rep = new Int8Array(V);
  const saved = new Int8Array(V * (F+1));
  let nodes = 0, leaves = 0, best = -Infinity, bestSet = null, T = 0;
  const chosen = [];
  const t0 = Date.now();
  let timedOut = false;

  function evaluate(){
    leaves++;
    let m = 127, sum = 0;
    for (let i=0;i<V;i++){ const v = rep[i]; sum += v; if (v < m) m = v; }
    const obj = (W*m + sum)*K + T;
    if (obj > best){ best = obj; bestSet = chosen.slice(); }
  }

  function dfs(idx, rem){
    nodes++;
    if ((nodes & 0xFFFFF) === 0 && Date.now()-t0 > timeLimitMs){ timedOut = true; }
    if (timedOut) return;
    if (idx >= F || rem < suffixMin[idx]){ evaluate(); return; }
    // branch 1: take film idx (films are runtime-sorted, so R[idx] <= rem is checked)
    if (R[idx] <= rem){
      const base = idx*V;
      for (let i=0;i<V;i++){
        saved[base+i] = rep[i];
        if (E[i][idx] && S[i][idx] > rep[i]) rep[i] = S[i][idx];
      }
      T += C[idx]; chosen.push(idx);
      dfs(idx+1, rem - R[idx]);
      chosen.pop(); T -= C[idx];
      for (let i=0;i<V;i++) rep[i] = saved[base+i];
    }
    // branch 2: skip film idx
    dfs(idx+1, rem);
  }
  dfs(0, B);
  return {nodes, leaves, best, bestSet: bestSet && bestSet.map(k=>ord[k]),
          ms: Date.now()-t0, timedOut};
}
module.exports = {enumerate};

if (require.main === module){
  const F = Number(process.env.F || 50), V = Number(process.env.V || 10);
  console.log(`| films | voters | budget | max slate | feasible slates | nodes | time | timed out |`);
  console.log(`|---|---|---|---|---|---|---|---|`);
  for (const B of (process.env.B ? [Number(process.env.B)] : [360, 480, 600, 720, 840, 960, 1080, 1440])){
    const inst = makeInstance({F, V, seed: 7});
    const res = enumerate(inst, B, {timeLimitMs: 60000});
    const maxCard = (()=>{ const r=[...inst.r].sort((a,b)=>a-b); let t=0,n=0; for(const x of r){ if(t+x>B) break; t+=x; n++; } return n; })();
    console.log(`| ${F} | ${V} | ${B} min (${(B/60).toFixed(0)}h) | ${maxCard} | ${res.leaves.toLocaleString()} | ${res.nodes.toLocaleString()} | ${res.ms} ms | ${res.timedOut ? '**yes, aborted at 60s**' : 'no'} |`);
  }
}
