// Instance generator for the slate-selection model defined in Z-Aether/ribcage#10.
// Deterministic PRNG so runs are reproducible.
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}

// Film runtimes: a realistic mix — mostly 90-130, a tail of long films.
function runtime(rnd){
  const u = rnd();
  if (u < 0.10) return 80  + Math.floor(rnd()*15);   // shorts / 80-94
  if (u < 0.65) return 95  + Math.floor(rnd()*30);   // the bulk / 95-124
  if (u < 0.90) return 125 + Math.floor(rnd()*25);   // 125-149
  return 150 + Math.floor(rnd()*60);                 // epics / 150-209
}

// Hand scores -1..+3. Skewed to the middle; +3 is rare but pluralisable.
function score(rnd){
  const u = rnd();
  if (u < 0.15) return -1;
  if (u < 0.50) return 0;
  if (u < 0.75) return 1;
  if (u < 0.91) return 2;
  return 3;
}

// F films, V voters. veto/seen rates are per (voter, film) pair.
function makeInstance({F=50, V=10, seed=1, vetoRate=0.02, seenRate=0.10}={}){
  const rnd = mulberry32(seed);
  const r = new Int32Array(F);
  for (let f=0; f<F; f++) r[f] = runtime(rnd);
  const s = [];       // s[i][f] in -2..3, -2 reserved for vetoes
  const elig = [];    // elig[i][f]: may f represent i?
  for (let i=0; i<V; i++){
    const si = new Int8Array(F), ei = new Uint8Array(F);
    for (let f=0; f<F; f++){
      const veto = rnd() < vetoRate;
      const seen = !veto && rnd() < seenRate;
      si[f] = veto ? -2 : score(rnd);
      ei[f] = (veto || seen) ? 0 : 1;
    }
    s.push(si); elig.push(ei);
  }
  // c[f] = total-term coefficient = sum over voters of s[i][f]
  const c = new Int32Array(F);
  for (let f=0; f<F; f++){ let t=0; for (let i=0;i<V;i++) t += s[i][f]; c[f]=t; }
  return {F, V, r, s, elig, c};
}
module.exports = {makeInstance};
