// Reproduces §5.2 of docs/research/movie-metadata.md.
//
// Question: can Wikidata serve as a silent fallback for a film's runtime when TMDB
// has none? It is keyless, CC0, and cross-walked to TMDB via property P4947, so it
// looked like the obvious answer. This checks whether the answer it gives is unique.
//
//   node docs/research/movie-metadata/wikidata-runtimes.js
//
// No dependencies, no key. Node 18+ (uses global fetch).
// WDQS requires a descriptive User-Agent with contact details; see
// https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/query_limits

const ENDPOINT = 'https://query.wikidata.org/sparql';
const UA = 'RibcageResearch/1.0 (https://github.com/Z-Aether/ribcage; szilardpeti@gmail.com)';

// Thirty films by TMDB id, deliberately canonical: if Wikidata is thin here it is
// thin everywhere. Several are known to exist in multiple cuts, which is the point.
const TMDB_IDS = [
  '429',    // The Good, the Bad and the Ugly
  '238',    // The Godfather
  '240',    // The Godfather Part II
  '155',    // The Dark Knight
  '27205',  // Inception
  '603',    // The Matrix
  '550',    // Fight Club
  '680',    // Pulp Fiction
  '13',     // Forrest Gump
  '120',    // LOTR: The Fellowship of the Ring
  '121',    // LOTR: The Two Towers
  '122',    // LOTR: The Return of the King
  '78',     // Blade Runner
  '335984', // Blade Runner 2049
  '62',     // 2001: A Space Odyssey
  '278',    // The Shawshank Redemption
  '105',    // Back to the Future
  '218',    // The Terminator
  '280',    // Terminator 2: Judgment Day
  '348',    // Alien
  '679',    // Aliens
  '694',    // The Shining
  '539',    // Psycho
  '389',    // 12 Angry Men
  '496243', // Parasite
  '11',     // Star Wars
  '1891',   // The Empire Strikes Back
  '807',    // Se7en
  '274',    // The Silence of the Lambs
  '510',    // One Flew Over the Cuckoo's Nest
];

const query = `
SELECT ?tmdb ?filmLabel
       (COUNT(DISTINCT ?d) AS ?nRuntimes)
       (GROUP_CONCAT(DISTINCT ?d; separator=", ") AS ?runtimes)
WHERE {
  VALUES ?tmdb { ${TMDB_IDS.map((id) => `"${id}"`).join(' ')} }
  ?film wdt:P4947 ?tmdb .
  OPTIONAL { ?film wdt:P2047 ?d }          # P2047 = duration
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
GROUP BY ?tmdb ?filmLabel
ORDER BY DESC(?nRuntimes)`;

async function main() {
  const url = `${ENDPOINT}?query=${encodeURIComponent(query)}&format=json`;
  const res = await fetch(url, {
    headers: { Accept: 'application/sparql-results+json', 'User-Agent': UA },
  });
  if (!res.ok) throw new Error(`WDQS returned ${res.status} ${res.statusText}`);
  const rows = (await res.json()).results.bindings;

  let missing = 0;
  let unique = 0;
  let ambiguous = 0;

  for (const row of rows) {
    const n = Number(row.nRuntimes.value);
    if (n === 0) missing++;
    else if (n === 1) unique++;
    else ambiguous++;

    const values = row.runtimes.value
      .split(', ')
      .map(Number)
      .sort((a, b) => a - b);
    const spread = n > 1 ? ` (spread ${values.at(-1) - values[0]} min)` : '';
    // The label service echoes the Q-id back when an item has no label in the
    // requested language, so a bare "Q12345" here means "no English label", not a bug.
    const label = row.filmLabel?.value ?? '?';
    console.log(
      `${String(n).padStart(2)}  tmdb=${row.tmdb.value.padEnd(7)}` +
        `${label.padEnd(48)}${values.join(', ') || '-'}${spread}`,
    );
  }

  console.log('-'.repeat(72));
  console.log(
    `films: ${rows.length}   no runtime: ${missing}   exactly one: ${unique}   ` +
      `ambiguous (>1): ${ambiguous}`,
  );
  console.log(
    'An ambiguous film is one Wikidata cannot answer without a human choosing a cut,\n' +
      'which is the editable runtime field the app needs anyway.',
  );
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
