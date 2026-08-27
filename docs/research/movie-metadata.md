# Movie metadata: which source, which fields, and where do trigger warnings come from?

Research for issue #5. Downstream consumers: #12 (timetable), #9 (voting interface), #16 (public access
and security posture), #15 (lifecycle and permissions).

**How the facts here were established, and how far to trust each one:**

- **TMDB — documentation only, not live-tested.** Every TMDB claim is quoted from TMDB's own developer
  docs, API reference, forum posts by TMDB staff, or the API Terms of Use, fetched 2026-08-27. No API key
  was used, by decision. Where the docs are silent — above all on *search ranking quality* — this is said
  plainly rather than guessed, and §10 ships a script that settles it in five minutes with your own key.
- **DoesTheDogDie — vendor docs, fetched directly.** Endpoint shapes, tiers, rate limits, attribution and
  the API Terms of Service were read off doesthedogdie.com's own pages on 2026-08-27. Not live-tested.
- **Wikidata — measured, live.** §5 runs real SPARQL against the public endpoint. Those numbers are
  reproducible: `node docs/research/movie-metadata/wikidata-runtimes.js`.

One measurement in here changed the recommendation, so it is worth flagging at the top: **30% of a
30-film canon sample carries more than one runtime in Wikidata, spread up to 63 minutes.** That is §5.

---

## 1. Verdict

**TMDB, for everything except trigger warnings. DoesTheDogDie for those. Nothing else earns a place.**

Three findings, in descending order of how much they should change the product:

1. **"The runtime of a film" is not a single fact, and this app is built on runtime.** The time budget is
   the solver's only hard constraint (#6), so a wrong runtime is not a cosmetic error — it silently
   produces an infeasible evening. Wikidata records 178, 208 *and* 228 minutes for *Fellowship of the
   Ring*; TMDB gives exactly one number per record, which is unambiguous but may not be the cut the group
   owns. **The runtime field must be editable by a human, always, and not merely as a fallback for
   missing data.** §5.
2. **Trigger warnings are gettable, free, self-serve, and keyed by TMDB id** — the DoesTheDogDie API v3
   accepts `?tmdb={id}` directly, so there is no second disambiguation problem. Free tier: 30 req/min,
   5,000 req/month, non-commercial only. The catch is not access, it is *shape*: what comes back is ~190
   topics of crowd-sourced yes/no vote counts, not a curated warning list. §6.
3. **SUGGEST is two HTTP calls, and the second one is a single request no matter how many fields you
   want.** `append_to_response` folds credits, videos and release_dates into the details call. §3.

**Manual entry is not the fallback — it is part of the design.** The ticket allowed "manual entry if
nothing viable exists". Something viable does exist, and manual entry is still required, for a different
reason: runtime is contested (§5) and DTDD's catalogue is crowd-sourced (§6.4). Both roads end at a
human-editable field, so build that field first and let the APIs pre-fill it.

**Cost: zero.** TMDB is free for non-commercial use; DTDD has a free tier; no paid tier is needed at any
point. The real price is paid in obligations, not money — attribution on every view that shows the data,
a public privacy policy, an abuse-report channel, and cache-expiry rules. §8.

---

## 2. Per-field availability

One `GET /3/movie/{id}?append_to_response=credits,videos,release_dates` returns everything in this table
except the trigger warnings. `append_to_response` takes "a comma separated list of endpoints within this
namespace, 20 items max" ([movie details reference](https://developer.themoviedb.org/reference/movie-details)),
and TMDB confirms it is one HTTP request:
["make sub requests within the same namespace in a single HTTP request"](https://developer.themoviedb.org/docs/append-to-response).

| Field | Source | Where in the response | Extra call? | Notes |
|---|---|---|---|---|
| Title | TMDB | `.title` | no | localised by `language` |
| Original title | TMDB | `.original_title` | no | **guaranteed present** — use it in the picker |
| Year | TMDB | `.release_date` (`YYYY-MM-DD`) | no | may be an empty string |
| **Runtime** | TMDB | `.runtime` (integer, minutes) | no | **may be `null` or `0`** — see §5 |
| Synopsis | TMDB | `.overview` | no | may be empty in a given language |
| Poster | TMDB | `.poster_path` | no | the image itself needs no key — §4 |
| Backdrop | TMDB | `.backdrop_path` | no | |
| Genres | TMDB | `.genres[].name` | no | |
| IMDb id | TMDB | `.imdb_id` | no | free cross-walk to other services |
| **Director** | TMDB | `.credits.crew[]` where `department == "Directing"` and `job == "Director"` | **append `credits`** | can be several people |
| **Trailer** | TMDB | `.videos.results[]` where `site == "YouTube"` and `type == "Trailer"` | **append `videos`** | also `official: bool`, `published_at`; filter and pick, don't take `[0]` |
| Age certification | TMDB | `.release_dates.results[]` → per-country `.certification` | **append `release_dates`** | a code only — `"R"`, `"18"` |
| Content descriptors | TMDB | same, `.descriptors[]` | **append `release_dates`** | sparse — §6.5 |
| Keywords | TMDB | `.keywords.keywords[].name` | append `keywords` | community tags, no documented quality bar |
| **Trigger warnings** | **DoesTheDogDie** | separate API, `?tmdb={id}` | **separate service** | §6 |

The response field lists above come from the TMDB API reference pages for
[movie details](https://developer.themoviedb.org/reference/movie-details),
[credits](https://developer.themoviedb.org/reference/movie-credits),
[videos](https://developer.themoviedb.org/reference/movie-videos),
[release dates](https://developer.themoviedb.org/reference/movie-release-dates) and
[keywords](https://developer.themoviedb.org/reference/movie-keywords).

---

## 3. The SUGGEST flow is two calls, and the first one cannot be skipped

TMDB's own workflow doc is explicit: *"First, you are going to issue a query to one of the movie, TV show
or person search methods"* and then *"you can use that id to query the movie details method"*
([search & query for details](https://developer.themoviedb.org/docs/search-and-query-for-details)).

```
GET /3/search/movie?query=dune                                       -> a list of candidates
GET /3/movie/438631?append_to_response=credits,videos,release_dates  -> everything in §2
GET https://www.doesthedogdie.com/api/v3/items?tmdb=438631           -> DTDD item id
GET https://www.doesthedogdie.com/api/v3/items/{itemId}              -> topic vote stats
```

**The consequential detail: `/search/movie` does not return runtime.** Its result objects carry only
`adult, backdrop_path, genre_ids, id, original_language, original_title, overview, popularity,
poster_path, release_date, title, video, vote_average, vote_count`
([search reference](https://developer.themoviedb.org/reference/search-movie)). Runtime lives on the
details endpoint alone — a TMDB moderator states it plainly, that runtime *"is only available via the
'get details' method"*.

So a picker showing five candidates cannot show their runtimes without five extra requests. That is fine,
and it is the right call anyway: **the picker's job is identity, not data.** Poster, title, year and
original title are enough to tell *Dune* 1984 from *Dune* 2021, and runtime arrives the moment one is
chosen.

At marathon scale the request count is nothing — a few hundred per marathon against a limit that sits
["somewhere in the 40 requests per second range"](https://developer.themoviedb.org/docs/rate-limiting)
(TMDB removed the old 40-per-10-seconds cap on 2019-12-16). Rate limiting is a non-issue for this app and
should not shape any design decision. Respect a `429` if one ever arrives.

### 3.1 Disambiguation is solved by showing a picker, not by being clever

TMDB's search is text-based and covers more than the display title: *"Searching by text takes into
account all original, translated, alternative names and titles"*
([finding data](https://developer.themoviedb.org/docs/finding-data)). So a user typing a translated title
or an alternative title will find the film.

Ranking is Elasticsearch relevance, not popularity. Travis Bell, TMDB staff,
[2015-12-31](https://www.themoviedb.org/talk/5684495ac3a36860e9018833):

> "Ultimately the search score (as calculated by Elasticsearch) is the most important."

Popularity acts as a boost on that score rather than as the sort key, and there is **no exact-match
mode** — client-side filtering is the documented advice if you need one.

Three consequences:

- **Never auto-select `results[0]`.** Nothing in the API guarantees the top hit is the intended film, and
  for remakes it frequently will not be. The correct handling of "Dune" is to show both.
- **A picker row needs `poster_path`, `title`, `release_date` and `original_title`** — all present in
  search results, no extra call. `original_title` is one of the handful of fields TMDB guarantees, and it
  is what separates *Oldboy* (2003) from *Oldboy* (2013) at a glance.
- **`primary_release_year` exists as a narrowing filter** and is worth wiring to an optional year box, but
  it should not be required — a user who types "dune 2021" into a single box should still get a picker
  rather than an error.

The docs offer no guidance at all on picking the right result, and this is the one claim in this document
that documentation genuinely cannot settle. §10 measures it.

---

## 4. Images need no key, and that simplifies things

Image URLs are `https://image.tmdb.org/t/p/{size}/{file_path}`
([image basics](https://developer.themoviedb.org/docs/image-basics)) — no authentication in the URL, so
posters can be rendered straight from the browser with a plain `<img src>`. Nothing has to proxy them.

The docs say the base URL and the size list *"can be retrieved by calling the `/configuration` API"*.
In practice that is one call at startup, or a hardcoded `w342` for a picker thumbnail with the answer
confirmed once via §10. The exact poster-size list is not enumerated in the prose docs and was not
verified without a key.

---

## 5. Runtime: the field everything depends on, measured

### 5.1 TMDB does not guarantee it

TMDB is fully crowd-sourced, and a moderator's answer on missing runtime is the honest statement of what
*is* guaranteed — only `id`, `original_language`, `original_title`, `adult`, `video`, `vote_count`,
`popularity` and `vote_average`:

> "This is quite common for non mainstream or older movies/TV shows, as TMDB is 100 % crowd sourced and
> there will always be some information missing. […] You must handle all missing data in your code."
> — talestalker, TMDB moderator, [2019-09-03](https://www.themoviedb.org/talk/5d6dca1165686e52e787d0dd)

Runtime is also affected by the `language` parameter — several forum reports describe `0` or `null`
runtimes when requesting less-populated languages. **Request `en-US` for the metadata call** even if the
UI is not English; it is the best-populated translation.

### 5.2 The bigger problem is not absence, it is disagreement — and it is common

Wikidata was the obvious free fallback for a missing runtime: keyless, CC0, and cross-walked to TMDB via
property `P4947`, so no extra id resolution is needed. It was tested live rather than assumed.

Thirty canonical films, looked up by TMDB id, counting *distinct* `P2047` (duration) values each
(`docs/research/movie-metadata/wikidata-runtimes.js`, run 2026-08-27):

| Distinct runtimes on record | Films | Examples |
|---|---|---|
| 0 (missing) | 0 of 30 | — |
| 1 | 21 of 30 | *Pulp Fiction* 154, *Parasite* 132, *The Matrix* 136 |
| **more than 1** | **9 of 30** | see below |

The nine ambiguous ones, with their competing values in minutes:

| Film | Runtimes on record | Spread |
|---|---|---|
| The Lord of the Rings: The Return of the King | 200, 250, 263 | **63 min** |
| The Lord of the Rings: The Two Towers | 179, 223, 235 | 56 min |
| The Lord of the Rings: The Fellowship of the Ring | 178, 208, 228 | 50 min |
| The Godfather Part II | 165, 202 | 37 min |
| The Shining | 119, 144 | 25 min |
| The Good, the Bad and the Ugly | 161, 177 | 16 min |
| Blade Runner | 112, 116 | 4 min |
| One Flew Over the Cuckoo's Nest | 133, 136 | 3 min |
| The Empire Strikes Back | 122, 124 | 2 min |

(A separate spot-check found *The Green Fog*, a 2017 Guy Maddin film, carrying a director, an IMDb id and
a TMDB id but **no `P2047` at all** — so absence happens too, just not in a canon sample.)

**This kills Wikidata as a silent automatic fallback.** A fallback that picks arbitrarily between 200 and
263 minutes for *Return of the King* would hand the solver a 63-minute lie about the single quantity its
one hard constraint is written in. The failure mode is invisible: the slate comes back labelled feasible
and the evening overruns by an hour.

### 5.3 What this actually means for the product

The finding generalises past Wikidata. **Extended editions, director's cuts, theatrical cuts and
restorations are different lengths of the same film**, and the group watches *one specific copy* of it.
No API knows which copy is in the room. TMDB's single scalar is unambiguous but not necessarily right.

Three consequences, in order of how load-bearing they are:

1. **Runtime is a human-editable field with an API-supplied default.** Not an edge-case fallback — the
   normal path. Someone who owns the extended *Fellowship* must be able to say 228.
2. **A candidate with no runtime cannot enter SOLVE.** The MILP's only hard constraint is
   `Σ r[f]·x[f] ≤ B` (#6); a null `r[f]` is not a smaller number, it is an undefined model. The natural
   place to enforce this is the APPROVE→VOTE transition, where the admin locks the candidate set: refuse
   to lock while any candidate has no runtime. That is a lifecycle rule and belongs to #15.
3. **Don't build the Wikidata fallback.** It costs a second integration and a SPARQL dependency, and on
   30% of a canon sample it would need a human to disambiguate anyway — which is the editable field you
   already built. Wikidata stays documented here as an escape hatch if manual entry proves annoying in
   practice, not as v1 scope. (If it is ever revisited: the endpoint is keyless and CC0, but it enforces
   a descriptive `User-Agent` with contact details, and 60s of query time per minute per IP.)

---

## 6. Trigger warnings: DoesTheDogDie, and it is better than expected

### 6.1 Access is self-serve and free

The API is at `https://www.doesthedogdie.com/api/v3`, documented at
[doesthedogdie.com/api/3.0](https://www.doesthedogdie.com/api/3.0). Auth is a single header:

> "All requests require an `X-API-KEY` header with your API key from your profile page." … "All responses
> are JSON. No `Accept` header required."

**No approval step, no email request.** The "Get free key" button on the
[data page](https://www.doesthedogdie.com/api) links to `/account/api/terms?next=/profile` — accept the
API terms, collect the key from your profile.

| Tier | Req/min | Req/month | Commercial use | Attribution |
|---|---|---|---|---|
| **Free** | 30 | 5,000 | **no** | required |
| Commercial | 600 | 500,000 | yes | required |

5,000 requests a month against a group that suggests maybe 40 films per marathon is three orders of
magnitude of headroom. Every response carries `X-RateLimit-Remaining-Minute` / `-Month`; a breach returns
`429` with `Retry-After`.

### 6.2 It speaks TMDB ids, which removes the whole disambiguation problem

```
GET /api/v3/items?tmdb=22660      # also ?imdb=, ?q=, ?name=&releaseYear=
GET /api/v3/items/{itemId}
```

An item carries `id, name, genres, releaseYear, itemTypeId, itemTypeName, tmdbId, imdbId, posterImage,
backgroundImage, overview`. **Because `?tmdb={id}` is a first-class lookup, the film the user already
disambiguated in the TMDB picker maps straight through.** No second search, no second picker, no fuzzy
title matching. This is the single fact that makes the integration cheap.

### 6.3 What comes back is votes, not verdicts

`GET /api/v3/items/{itemId}` returns a `topicItemStats` array:

```json
{ "topicItemId": 395866, "yesSum": 57, "noSum": 3, "numComments": 7,
  "topicId": 153, "topicName": "a dog dies", "itemId": 10752 }
```

Supporting endpoints: `/api/v3/topics` (the full topic vocabulary — `name`, `notName`, `description`,
`keywords`, `topicCategoryId`), `/api/v3/topiccategories`, `/api/v3/topicsupercategories`,
`/api/v3/itemtypes`, and `/api/v3/items/{id}/ratings?topicId={id}` for individual comments and
community timestamps.

The [data page](https://www.doesthedogdie.com/api) lists **193 topics across 53 categories**, grouped into
super-categories like "Disturbing Content" and "Emotional Spoilers". Topic names are concrete and uneven
in register — "a dog dies", "blood or gore", "gaslighting", "car honk / tire screech", "sexual assault".

**This is not a warning list you can render.** `57 yes / 3 no` is a crowd's opinion, and 193 topics per
film is an unreadable wall. Turning it into something a person can act on — which topics to show, what
vote ratio counts as a warning, whether each user declares the topics they care about — is a product
decision, not a fetching problem. It is ticketed separately.

Two smaller shape facts: `/ratings` returns only ratings *"with a comment, cue description, or
timestamp"* — bare yes/no votes are excluded — and professionally-produced **Scene Alerts** (precise
timestamps, skip-to points) are filtered out entirely on the free tier; they are a paid Commercial add-on
requiring a separate written agreement under §9.3 of the API terms. Community timestamps and comments
*are* included on Free.

### 6.4 Coverage: large, crowd-sourced, and mainstream-skewed

From DTDD's own published figures (fetched 2026-08-27): **74,789 titles covered, of which 47,202 are
movies**, built from 19,607,054 community yes/no ratings and 885,926 comments. For scale, only 158 movies
have Scene Alerts — irrelevant here, since those are paid anyway.

47,202 movies is a large catalogue but a crowd-sourced one, and no completeness claim is made anywhere in
the docs. Expect gaps on obscure, foreign and older films — precisely the corners a film-literate friend
group tends to enjoy. **How well it covers *this group's* taste is not answerable from documentation**,
and it changes how prominent the feature should be. That is a five-minute empirical question with a free
key, and it is ticketed as a task.

### 6.5 TMDB's own `descriptors` are a real but thin consolation

`/movie/{id}/release_dates` has a `descriptors` array alongside `certification`. TMDB staff, via
moderator lineker quoting Travis Bell:

> "These are the 'rating descriptors' or 'rating reasons'. Some countries mandate these as part of the
> rating laws around content."
> — [TMDB forum, thread opened 2023-01-10](https://www.themoviedb.org/talk/63bcd118a6e2d20083e25c74)

They appear *"only on the countries we have added support for"*, so most releases have an empty array.
This is a free extra — it rides along on a call you are already making — but it is a coarse regulatory
tag, not a trigger warning. Take it if present, never depend on it.

---

## 7. Everything else, and why it is out

| Source | Status | Reason |
|---|---|---|
| **OMDb** | ruled out | Free key, 1,000 req/day, but `Runtime` is a string (`"137 min"`) needing parsing, and its [terms](https://www.omdbapi.com/legal.htm) forbid indexing or building derivative databases from its contributions. Adds nothing TMDB lacks. |
| **Wikidata** | documented, not built | §5.3. Keyless, CC0, `P4947` cross-walk — genuinely nice, but ambiguous on 30% of a canon sample for the one field it was wanted for. |
| **Wikipedia REST** | ruled out | Runtime lives in rendered infobox markup, not a structured field. Wikidata *is* the structured version of this. |
| **JustWatch** | no public API | Partner/commercial only, via `data-partner@justwatch.com`. Streaming availability anyway, not runtime or director. |
| **Letterboxd** | ruled out | Still approval-gated in 2026 — email `api@letterboxd.com` and wait. Runtime presence unconfirmed. Not worth a manual gate. |
| **Trakt.tv** | ruled out | Free app registration, 500 GET/5min, but runtime only via `?extended=full` and it hosts no images. Its value is id cross-walking, which TMDB already provides via `imdb_id`. |
| **IMDb non-commercial datasets** | ruled out | `title.basics.tsv.gz` genuinely has `runtimeMinutes`, but it is a bulk daily TSV, not a live API, and the [terms](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX/) forbid repurposing it into "any kind of online/offline database of movie information". Wrong shape and legally murky. |
| **IMDb commercial API** | ruled out | Licensed via AWS Data Exchange at enterprise pricing. |
| **TheTVDB** | ruled out | No free self-serve tier — negotiate a licence, or every end user needs their own paid subscription PIN. |
| **Unconsenting Media** | no API | Narrower scope (sexual violence), web-only, no documented export. Would require scraping. |
| **Common Sense Media** | ruled out | A real API exists, but *"API keys are granted upon initiation of a partnership agreement"* — partnership-gated, built for bulk syndication. |
| **BBFC / Kijkwijzer / MPA** | no API | BBFC publishes per-film content advice as HTML only; the MPA publishes a static glossary of descriptor terms, not a per-film lookup. Nothing programmatic. |

---

## 8. Terms: what the free access actually costs

Money, nothing. Obligations, several — and two of them shape the UI.

### 8.1 TMDB

- **Non-commercial is free.** *"Our API is free to use for non-commercial purposes as long as you
  attribute TMDB as the source of the data and/or images."* Commercial is defined as *"if the primary
  purpose is to create revenue for the benefit of the owner"*
  ([FAQ](https://developer.themoviedb.org/docs/faq)). A private app for ten friends is comfortably inside
  this.
- **Attribution is mandatory**: display the TMDB logo, less prominent than your own branding, plus the
  notice *"This product uses the TMDB API but is not endorsed or certified by TMDB."* Logos and brand
  colours: [themoviedb.org/about/logos-attribution](https://www.themoviedb.org/about/logos-attribution).
- **Caching is capped at six months** — the [Terms of Use](https://www.themoviedb.org/api-terms-of-use)
  prohibit caching *"for longer than 6 months"*. Irrelevant under the clean-slate rule: no marathon lasts
  six months.
- **Keys are self-serve** — request one from the API section of account settings; no approval process is
  documented for non-commercial use, and the dev has already obtained one for another project.
- Either the **v3 API key** (query string `api_key=`) or the **v4 read access token**
  (`Authorization: Bearer …`) works; *"both authentication methods provide the same level of access"*,
  with Bearer described as the default
  ([authentication](https://developer.themoviedb.org/docs/authentication-application)). Prefer Bearer —
  it keeps the credential out of URLs and therefore out of logs.

### 8.2 DoesTheDogDie — read this one properly

Per the [API Terms of Service](https://www.doesthedogdie.com/api/terms):

- **§6 Attribution, and it is stricter than TMDB's.** The exact phrase **"Powered by DoesTheDogDie.com"**,
  hyperlinked, *"wherever the Company Offering is displayed in Your Application"* — the API docs sharpen
  this to *"every screen, page, or view that shows it, not just an about page or a footer on your
  homepage"*. **Any other wording requires written approval first.** Concretely: if a movie card shows
  trigger warnings, that card carries the credit. This is a UI constraint, not a footer item, and it
  lands on #9 and on the SUGGEST-screen prototype.
- **§9.1 Free tier is non-commercial only** — no user fees, no advertising, sponsorship, affiliate
  arrangements or data sales, not operated for a for-profit business. Fine here.
- **§3, final clause: cached data must be refreshed at least every 30 days**, and deleted on termination
  (§14.4). Note the interaction with the seasonal model from #7: a marathon window is ~4 weeks, so data
  fetched at SUGGEST is at most ~28 days old at RUN — **inside the limit, with about two days of slack.**
  That is the same shape of margin as Render's 30-day free-tier clock, and it argues for re-fetching at
  PICK rather than trusting SUGGEST-time data through to RUN. Simplest safe answer: don't persist DTDD
  payloads across phases at all; the request budget makes re-fetching free.
- **§2.4(b) requires "a clear, publicly accessible privacy policy"** for the application, and **§5
  requires "a resource for users of your Applications to report abuse"**. These are unconditional
  covenants, not commercial-tier extras. For a ten-person private app the privacy surface is nearly nil,
  but the clauses do not care — a small, real compliance cost, and it belongs in front of #16.
- §3 also forbids ML training on the data, systematic harvesting, and *"misrepresent[ing] the source,
  accuracy, or completeness of the Data"* — the last one is worth remembering when designing how vote
  counts get summarised into a warning (§6.3). Rendering `57 yes / 3 no` as a flat "this film contains…"
  is arguably exactly that.

---

## 9. What this constrains downstream

- **#12 (timetable)** — runtime is user-editable with a TMDB default, and "the runtime" is a property of
  *the group's copy*, not of the film. §5.3.
- **#15 (lifecycle)** — the APPROVE→VOTE lock should refuse a candidate set containing a film with no
  runtime, because SOLVE's only hard constraint is undefined without it. §5.3.
- **#9 (voting interface)** — any view rendering DTDD data must carry the "Powered by DoesTheDogDie.com"
  credit; a movie card showing trigger warnings is such a view. §8.2.
- **#16 (public access)** — DTDD's free tier obliges a publicly accessible privacy policy and an
  abuse-report channel. §8.2.
- **#14 (tech stack)** — **no constraint.** Both APIs are plain authenticated JSON over HTTPS; posters are
  keyless CDN URLs. Nothing here favours any language, framework or hosting platform. Note only that both
  keys are server-side secrets and must not ship to the browser, which rules out a purely static
  front-end talking directly to TMDB — but every candidate stack in #7 has a server.
- **Nothing here bears on #17 or #18.**

---

## 10. Verifying this with a key, in five minutes

This research was done without an API key, so the claims only a live call can settle are marked as such
above. `docs/research/movie-metadata/verify.js` settles them. No dependencies, Node 18+:

```
TMDB_TOKEN=<v4 read access token> node docs/research/movie-metadata/verify.js
DTDD_KEY=<free key> TMDB_TOKEN=<token> node docs/research/movie-metadata/verify.js
```

It checks the four things documentation could not:

1. **Disambiguation** — searches deliberately hard titles (*Dune*, *Nosferatu*, *Solaris*, *The Thing*,
   *Suspiria*, *Oldboy*, *Total Recall*, *Funny Games*, *Insomnia*, *Cure*) and prints the top five with
   year and popularity, so you can see for yourself whether a picker is required and how many rows it
   needs. §3.1 assumes it is; this proves it.
2. **One-call completeness** — fetches details with `append_to_response=credits,videos,release_dates` and
   reports whether runtime, director, trailer, certification and descriptors actually arrived.
3. **Runtime nullability** — the same check over deliberately obscure films, which is where §5.1 predicts
   TMDB thins out.
4. **DTDD coverage** (if `DTDD_KEY` is set) — looks each film up by `?tmdb={id}` and reports the hit rate
   and how many topics carry votes. This is the measurement §6.4 says is needed, and it is the instrument
   for the coverage task ticket.

Point it at a list of films the group would *actually* suggest, not this canon list. That is the only
version of the coverage question that matters.
