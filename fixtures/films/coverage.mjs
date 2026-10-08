// Ticket #19: measure DTDD coverage + TMDB picker/runtime facts against the
// group's REAL shortlist (past_movies.txt — three past marathons).
import fs from 'node:fs';

const TMDB = process.env.TMDB_TOKEN;
const DTDD_KEY = process.env.DTDD_KEY;
const USE_BEARER = TMDB.split('.').length === 3;

const raw = fs.readFileSync(process.argv[2], 'utf8');

// Parse "Title (YYYY)" / "Title" — keep the string as the group actually wrote it.
const seen = new Map();
for (const line of raw.split(/\r?\n/)) {
  const s = line.trim();
  if (!s) continue;
  const m = s.match(/^(.*?)\s*\((\d{4})\)\s*$/);
  const title = (m ? m[1] : s).trim();
  const y = m ? Number(m[2]) : null;
  const key = title.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (!seen.has(key)) seen.set(key, { asWritten: s, title, year: y });
  else if (y && !seen.get(key).year) seen.get(key).year = y;
}
const FILMS = [...seen.values()];

// Strip the group's shorthand. Only used as a SECOND attempt.
function clean(t) {
  let s = t.replace(/\s*\((?!\d{4}\))[^)]*\)\s*$/, '');
  s = s.replace(/\s*\/\s*.*$/, '');
  s = s.replace(/^[A-Z]{2,4}:\s*/, '');
  s = s.replace(/^[A-Z][\w.' ]+?'s\s+/, '');
  return s.trim();
}

async function tmdb(path, params = {}) {
  const url = new URL(`https://api.themoviedb.org/3${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const headers = { accept: 'application/json' };
  if (USE_BEARER) headers.Authorization = `Bearer ${TMDB}`;
  else url.searchParams.set('api_key', TMDB);
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`TMDB ${path} -> ${res.status}`);
  return res.json();
}
// Free tier is 30 req/min, so pace every DTDD call at ~28/min.
let dtddNext = 0;
async function dtdd(path) {
  const wait = dtddNext - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  dtddNext = Date.now() + 2150;
  const res = await fetch(`https://www.doesthedogdie.com/api/v3${path}`, {
    headers: { 'X-API-KEY': DTDD_KEY },
  });
  if (!res.ok) throw new Error(`DTDD ${res.status}`);
  return { body: await res.json(), hdr: res.headers };
}
const yr = (d) => (d ? Number(d.slice(0, 4)) : null);
const pad = (s, n) => String(s).slice(0, n).padEnd(n);

const rows = [];
console.log('=== A. SUGGEST search: what a user typing the group own words gets ===\n');
console.log(`${pad('as written', 40)} ${pad('n', 3)} ${pad('results[0]', 34)} verdict`);
console.log('-'.repeat(115));

for (const f of FILMS) {
  const row = { ...f };
  let q = f.title;
  let r = await tmdb('/search/movie', { query: q, language: 'en-US' });
  let retried = false;
  const yearNear = (list) => f.year && list.slice(0, 5).some((m) => Math.abs(yr(m.release_date) - f.year) <= 1);
  if (!r.results.length || (f.year && !yearNear(r.results))) {
    const c = clean(f.title);
    if (c && c !== f.title) {
      const r2 = await tmdb('/search/movie', { query: c, language: 'en-US' });
      if (r2.results.length && (!f.year || yearNear(r2.results))) { r = r2; q = c; retried = true; }
    }
  }
  row.query = q; row.retried = retried; row.nResults = r.results.length;

  if (!r.results.length) {
    row.status = 'NOT FOUND'; rows.push(row);
    console.log(`${pad(f.asWritten, 40)} ${pad(0, 3)} ${pad('-', 34)} NOT FOUND`);
    continue;
  }

  const top5 = r.results.slice(0, 5);
  const meant = f.year
    ? (top5.find((m) => yr(m.release_date) === f.year)
       ?? top5.find((m) => Math.abs(yr(m.release_date) - f.year) <= 1)
       ?? r.results.find((m) => yr(m.release_date) === f.year))
    : null;
  const pick = meant ?? r.results[0];
  row.id = pick.id;
  row.pick = `${pick.title} (${yr(pick.release_date)})`;
  row.autoOk = !f.year ? null : pick.id === r.results[0].id;
  row.meantInTop5 = meant ? top5.some((m) => m.id === meant.id) : null;
  row.exactTitleDupes = r.results.filter((m) => m.title.toLowerCase() === q.toLowerCase()).length;
  row.top5 = top5.map((m) => `${m.title} (${yr(m.release_date)})`);
  row.status = 'ok';
  rows.push(row);

  const verdict = row.autoOk === null ? 'no year given'
    : row.autoOk ? 'auto-pick OK'
    : `AUTO-PICK WRONG -> "${r.results[0].title} (${yr(r.results[0].release_date)})"`;
  console.log(`${pad(f.asWritten, 40)} ${pad(r.results.length, 3)} ${pad(`${r.results[0].title} (${yr(r.results[0].release_date)})`, 34)} ${verdict}${retried ? `  [retried as "${q}"]` : ''}`);
}

console.log('\n\n=== B. Details call: runtime nullability + one-call completeness ===\n');
console.log(`${pad('film', 34)} runtime  dir trailer cert   descr genres`);
console.log('-'.repeat(100));
for (const row of rows) {
  if (row.status !== 'ok') continue;
  const m = await tmdb(`/movie/${row.id}`, { language: 'en-US', append_to_response: 'credits,videos,release_dates' });
  const dir = m.credits?.crew?.find((c) => c.job === 'Director');
  const tr = m.videos?.results?.find((v) => v.site === 'YouTube' && v.type === 'Trailer');
  const us = m.release_dates?.results?.find((x) => x.iso_3166_1 === 'US');
  const cert = us?.release_dates?.find((x) => x.certification)?.certification;
  const desc = us?.release_dates?.flatMap((x) => x.descriptors ?? []) ?? [];
  row.runtime = m.runtime; row.dir = !!dir; row.trailer = !!tr; row.cert = cert || null;
  row.descriptors = desc.length; row.genres = (m.genres || []).map((g) => g.name);
  row.poster = !!m.poster_path; row.overview = !!m.overview; row.imdb = m.imdb_id || null;
  console.log(`${pad(row.pick, 34)} ${String(m.runtime ?? 'NULL').padStart(5)}    ${dir ? 'y' : 'N'}   ${tr ? 'y' : 'N'}     ${pad(cert || '-', 6)} ${String(desc.length).padStart(3)}   ${row.genres.join('/')}`);
}

console.log('\n\n=== C. DoesTheDogDie coverage by TMDB id ===\n');
console.log(`${pad('film', 34)} ${pad('dtdd', 6)} voted netyes strong  top topics`);
console.log('-'.repeat(120));
let hits = 0, total = 0, lastHdr;
for (const row of rows) {
  if (row.status !== 'ok') continue;
  total++;
  let items;
  try { const r = await dtdd(`/items?tmdb=${row.id}`); items = r.body; lastHdr = r.hdr; }
  catch (e) { row.dtdd = `ERROR ${e.message}`; console.log(`${pad(row.pick, 34)} ${e.message}`); continue; }
  const list = Array.isArray(items) ? items : (items?.items ?? []);
  if (!list.length) { row.dtdd = 'miss'; console.log(`${pad(row.pick, 34)} ${pad('MISS', 6)}`); continue; }
  hits++;
  const d = await dtdd(`/items/${list[0].id}`); lastHdr = d.hdr;
  const stats = d.body.topicItemStats ?? [];
  const voted = stats.filter((s) => s.yesSum + s.noSum > 0);
  const flagged = stats.filter((s) => s.yesSum > s.noSum);
  const strong = voted.filter((s) => s.yesSum + s.noSum >= 5);
  row.dtdd = 'hit'; row.dtddId = list[0].id; row.dtddName = list[0].name;
  row.voted = voted.length; row.flagged = flagged.length; row.strong = strong.length;
  row.totalTopics = stats.length;
  row.topTopics = [...flagged].sort((a, b) => b.yesSum - a.yesSum).slice(0, 3).map((s) => `${s.topicName} ${s.yesSum}/${s.yesSum + s.noSum}`);
  console.log(`${pad(row.pick, 34)} ${pad('hit', 6)} ${String(voted.length).padStart(5)} ${String(flagged.length).padStart(6)} ${String(strong.length).padStart(6)}   ${row.topTopics.join('; ') || '-'}`);
}

console.log(`\n-> DTDD coverage: ${hits}/${total}`);
if (lastHdr) console.log(`-> rate limit remaining: minute=${lastHdr.get('x-ratelimit-remaining-minute')} month=${lastHdr.get('x-ratelimit-remaining-month')}`);
fs.writeFileSync(process.argv[3], JSON.stringify(rows, null, 2));
