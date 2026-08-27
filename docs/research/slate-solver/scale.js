// Headroom: how far past the stated 50-film / 10-voter ceiling does the MILP hold up?
const {makeInstance} = require('./instance.js');
const {buildLP} = require('./mip.js');
(async () => {
  const highs = await require('highs')();
  highs.solve('Maximize\n obj: x\nSubject To\n c: x <= 1\nBounds\n 0 <= x <= 1\nEnd');
  console.log('| films | voters | budget | binaries | rows | solve time |');
  console.log('|---|---|---|---|---|---|');
  for (const [F,V,B] of [[50,10,720],[50,10,1440],[100,10,1440],[200,10,1440],[500,10,1440],[100,25,1440],[200,50,2880]]){
    const inst = makeInstance({F,V,seed:7});
    const lp = buildLP(inst, B);
    const nbin = (lp.match(/Binaries\n (.*)/)||['',''])[1].split(/\s+/).filter(Boolean).length;
    const nrow = (lp.split('Subject To')[1].split('Bounds')[0].match(/\n/g)||[]).length - 1;
    const t0 = process.hrtime.bigint();
    const res = highs.solve(lp, {mip_rel_gap:0, mip_abs_gap:0});
    const ms = Number(process.hrtime.bigint()-t0)/1e6;
    console.log(`| ${F} | ${V} | ${B} | ${nbin} | ${nrow} | ${res.Status==='Optimal' ? `**${ms.toFixed(0)} ms**` : res.Status} |`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
