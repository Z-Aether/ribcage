// Settles the claims in docs/research/movie-metadata.md that documentation cannot.
//
// The research behind that document was done without an API key, deliberately. Four
// things therefore rest on TMDB's docs rather than on observation, and all four are
// cheap to check for real:
//
//   1. does /search/movie need a picker, or is results[0] reliable?   (§3.1)
//   2. does one append_to_response call really return every field?    (§2)
//   3. how often is runtime null or 0 on obscure films?               (§5.1)
//   4. how much of this group's taste does DoesTheDogDie cover?       (§6.4)
//
// Usage:
//   TMDB_TOKEN=<v4 read access token> node docs/research/movie-metadata/verify.js
//   TMDB_TOKEN=... DTDD_KEY=<free key> node docs/research/movie-metadata/verify.js
//
// The v3 api_key works too — pass it as TMDB_TOKEN and the script falls back to the
// query-string form. No dependencies. Node 18+ (uses global fetch).
//
// Check 4 is the one that matters most: replace OBSCURE below with films this group
// would actually suggest. Coverage of a canon list tells you nothing useful.

const TMDB_TOKEN = process.env.TMDB_TOKEN;
const DTDD_KEY = process.env.DTDD_KEY;

if (!TMDB_TOKEN) {
  console.error('Set TMDB_TOKEN (v4 read access token, or a v3 api_key).');
  process.exit(1);
}

// A v4 read access token is a JWT and always has two dots; a v3 key never does.
const USE_BEARER = TMDB_TOKEN.split('.').length === 3;

// Titles chosen to be genuinely ambiguous: remakes, shared titles, translated titles.
const HARD_SEARCHES = [
  'Dune',
  'Nosferatu',
  'Solaris',
  'The Thing',
  'Suspiria',
  'Oldboy',
  'Total Recall',
  'Funny Games',
  'Insomnia',
  'Cure',
];

// Deliberately off the beaten track — where §5.1 predicts TMDB thins out.
// Swap these for the group's real shortlist before trusting the DTDD number.
const OBSCURE = [
  'The Green Fog',
  'Hausu',
  'Sátántangó',
  'The Colour of Pomegranates',
  'Wake in Fright',
  'Daisies',
  'The Cremator',
  'Vampyr',
  'World on a Wire',
  'Come and See',
];

async function tmdb(path, params = {}) {
  const url = new URL(`https://api.themoviedb.org/3${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const headers = { accept: 'application/json' };
  if (USE_BEARER) headers.Authorization = `Bearer ${TMDB_TOKEN}`;
  else url.searchParams.set('api_key', TMDB_TOKEN);

  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`TMDB ${path} -> ${res.status} ${res.statusText}`);
  return res.json();
}

async function dtdd(path) {
  const res = await fetch(`https://www.doesthedogdie.com/api/v3${path}`, {
    headers: { 'X-API-KEY': DTDD_KEY },
  });
  if (!res.ok) throw new Error(`DTDD ${path} -> ${res.status} ${res.statusText}`);
  return res.json();
}

const year = (d) => (d ? d.slice(0, 4) : '????');

// 1. Does search need a picker? Print the top five and judge for yourself.
async function checkDisambiguation() {
  console.log('\n=== 1. Search: is a picker required? (§3.1) ===\n');
  for (const q of HARD_SEARCHES) {
    const { results } = await tmdb('/search/movie', { query: q, language: 'en-US' });
    const top = results.slice(0, 5);
    console.log(`"${q}" — ${results.length} results, top 5:`);
    for (const [i, m] of top.entries()) {
      const orig = m.original_title !== m.title ? `  [${m.original_title}]` : '';
      console.log(
        `   ${i + 1}. ${year(m.release_date)}  ${m.title}${orig}` +
          `  (pop ${m.popularity.toFixed(1)}, poster ${m.poster_path ? 'yes' : 'NO'})`,
      );
    }
    // The claim under test: how often would auto-picking results[0] be defensible?
    const sameTitle = top.filter(
      (m) => m.title.toLowerCase() === q.toLowerCase(),
    ).length;
    if (sameTitle > 1) console.log(`   -> ${sameTitle} exact-title matches; auto-pick would guess.`);
    console.log();
  }
}

// 2 + 3. One call, every field — and how often runtime is simply absent.
async function checkFields(titles, label) {
  console.log(`\n=== ${label} ===\n`);
  let noRuntime = 0;
  const found = [];

  for (const title of titles) {
    const { results } = await tmdb('/search/movie', { query: title, language: 'en-US' });
    if (!results.length) {
      console.log(`${title.padEnd(30)} NOT FOUND on TMDB`);
      continue;
    }
    const id = results[0].id;
    const m = await tmdb(`/movie/${id}`, {
      language: 'en-US',
      append_to_response: 'credits,videos,release_dates',
    });

    const director = m.credits?.crew?.find(
      (c) => c.department === 'Directing' && c.job === 'Director',
    );
    const trailer = m.videos?.results?.find(
      (v) => v.site === 'YouTube' && v.type === 'Trailer',
    );
    const us = m.release_dates?.results?.find((r) => r.iso_3166_1 === 'US');
    const cert = us?.release_dates?.find((r) => r.certification)?.certification;
    const descriptors = us?.release_dates?.flatMap((r) => r.descriptors ?? []) ?? [];

    if (!m.runtime) noRuntime++;
    found.push({ id, title: m.title });

    console.log(
      `${m.title.slice(0, 28).padEnd(30)} ` +
        `runtime=${String(m.runtime ?? 'NULL').padStart(4)}  ` +
        `dir=${director ? 'yes' : 'NO '}  ` +
        `trailer=${trailer ? 'yes' : 'NO '}  ` +
        `cert=${(cert || '-').padEnd(5)} ` +
        `descriptors=${descriptors.length}`,
    );
  }

  console.log(`\n-> ${noRuntime}/${titles.length} had no usable runtime.`);
  return found;
}

// 4. The measurement that decides how prominent trigger warnings should be.
async function checkDtddCoverage(films) {
  console.log('\n=== 4. DoesTheDogDie coverage by TMDB id (§6.4) ===\n');
  let hits = 0;

  for (const { id, title } of films) {
    let items;
    try {
      items = await dtdd(`/items?tmdb=${id}`);
    } catch (err) {
      console.log(`${title.slice(0, 28).padEnd(30)} ERROR ${err.message}`);
      continue;
    }
    if (!items?.length) {
      console.log(`${title.slice(0, 28).padEnd(30)} not in catalogue`);
      continue;
    }
    hits++;
    const detail = await dtdd(`/items/${items[0].id}`);
    const stats = detail.topicItemStats ?? [];
    const voted = stats.filter((s) => s.yesSum + s.noSum > 0);
    const flagged = stats.filter((s) => s.yesSum > s.noSum);
    console.log(
      `${title.slice(0, 28).padEnd(30)} ` +
        `topics with votes: ${String(voted.length).padStart(3)}  ` +
        `net-yes: ${String(flagged.length).padStart(3)}  ` +
        `e.g. ${flagged.slice(0, 3).map((s) => s.topicName).join('; ') || '-'}`,
    );
    // Free tier is 30 req/min; two calls per film, so pace it.
    await new Promise((r) => setTimeout(r, 250));
  }

  console.log(
    `\n-> ${hits}/${films.length} covered. ` +
      'Below about half, trigger warnings are a manual-entry feature with an assist,\n' +
      '   not an auto-filled one.',
  );
}

async function main() {
  await checkDisambiguation();
  await checkFields(HARD_SEARCHES, '2. One append_to_response call, mainstream films (§2)');
  const obscure = await checkFields(OBSCURE, '3. Runtime nullability, obscure films (§5.1)');

  if (!DTDD_KEY) {
    console.log('\n=== 4. DTDD coverage — skipped, no DTDD_KEY set ===');
    console.log('Free key: https://www.doesthedogdie.com/api -> "Get free key".');
    return;
  }
  await checkDtddCoverage(obscure);
}

main().catch((err) => {
  console.error(`\n${err.message}`);
  process.exit(1);
});
