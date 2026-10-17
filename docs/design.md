# Ribcage — design overview

The whole shape of the app in one place: why it exists, the principles it is built on, the workflow it implements, and every surface and module that workflow needs. Not an implementation spec. Condensed from the wayfinder map ([#4](https://github.com/Z-Aether/ribcage/issues/4)) and its closed sub-tickets as of 2026-10-11.

- Terms are used as defined in [`GLOSSARY.md`](../GLOSSARY.md). Read it alongside this.
- Ticket numbers (#n) point at the decision of record. A ticket's last dated amendment comment overrides the text above it. Where this doc and a ticket disagree, the ticket wins; flag the conflict.

---

## 1. What and why

A web app for a fixed group of 5–10 friends who hold a film marathon about three times a year. It replaces a freely editable Google Sheet.

The group's problem is **not finding a date**. The date is the admin's input. The problem is agreeing on a **slate** that serves everyone within a time **budget**, then arranging and running the evening.

- **One running copy per marathon.** The app is rebuilt at the start of a ~4-week **window**, used for one marathon, and destroyed at **teardown**. Nothing carries over: no voters, no films, no history. There is no Marathon entity; the database itself is the scope (#8, #15, #30).
- **Representation, not total enjoyment.** The dev's old process was "get everyone's #1 in unless it conflicts, then balance the rest". A flat sum lets mild approval outbid one person's passion and produces a slate nobody minds and nobody wanted. SOLVE instead maximises the worst-served voter's best film first (#10).
- **Small and seasonal.** Tiny fixed scale, switched off eight months a year. It must be non-sloppy and cheaply extensible, not production-grade.
- **Educational goal:** web-dev design and architecture fundamentals on well-trodden paths. Integer optimisation is a stated interest and earned its place on the budget, not on difficulty (#6).

---

## 2. Principles

### Product

- **Honest display, not curation.** Show every proposal with its **standing**. Ties are **tiers**, losses are losses, and a short **batch** means the space is short. Nothing is padded or filtered out, and every failure is shown with its reason (#17).
- **No silent wrong answer.** The map's recurring trap is a result that is quietly wrong but labelled `Optimal`: an absent ballot pinning the floor at 0, `results[0]` taken from search, a flagged admin skewing `min(rep)`. Exclusions are always shown with a reason, such as the **floor set** line (#10, #15, #25).
- **The tool never says no, but it never hides a consequence.** **Overlap** is flagged, not prevented. The **budget** is a marker in PICK, not a gate. A hand-built slate over budget is allowed. Readouts recompute live and identically for solved and hand-edited slates (#12).
- **Social norms, not hardcoded referees.** Vetoes are uncapped because they are **attributed** and visible. Registration has no approval queue, because the **roster** catches mistakes afterwards. Who holds the admin password is a social question, not a coded one (#8, #10).
- **An edge case that needs its own surface isn't worth handling.** Prefer a generalisation that already covers it. Examples: notes cover films with no DTDD data, manual entry covers TV series, shell access covers break-glass (#15).
- **The voter side never deals with clock time.** No voter is ever asked about clock time or attendance. Time enters only at PICK, on the admin's side, through the **anchor** (#11, #12).
- **Derived over stored. One copy of the truth.** **Now playing**, **presence strips**, the **phase**, and whether the **reveal** has happened are all derived, never kept as their own state. **Actualising** means editing the **timetable**, not recording what happened (#13, #26).
- **Preview over undo.** There is no undo anywhere and no confirmation modals by default. Drags, **arrange utilities** and **Use this slate** show a **preview** before anything changes. Phase moves are a click and then an inline confirm (#22, #28, #39).
- **Manual, attended transitions.** All four phase moves are admin clicks. There are no deadlines, no scheduler, no email and no push. The **done** roster and the group chat are the nudge (#15).
- **People choose, APIs only suggest.** A person picks which film they meant in the **picker**; search ranking never decides. **Runtime** and the DTDD match are fields people can edit, with API defaults (#5, #19).
- **The group's own words over official metadata.** **Notes** and the **pitch** replace synopsis and genres (#21).
- **Minimal personal data.** The **display name** is the only personal detail, and there is no email field. The **watched list** is private, even from the admin. The app promises "not shown to the group", never "anonymous" (#8, #20).

### Interface

- **Voter surfaces are rounded, roomy and uncluttered. Admin surfaces are utilitarian.** Voters read SUGGEST, VOTE, the reveal and RUN. One admin at a desk reads the console and PICK, which use dense ledgers (#29).
- **Intuitive or out.** A layout whose navigation needs explaining loses. Shared components beat view-specific ones (the **film card** everywhere). Things open in place, never as sheets. Posters are non-negotiable (#9, #21).
- **Dense ledgers for admin work.** One row per item, expanded inline, tabs rather than side panels. Matrices, cards and wide layouts lost every comparison (#24, #28).
- **Explicit stepped flows** over instant actions (#21).
- **Desktop-first. Only RUN must be good on a phone** (#14).
- **One theme across every surface,** settled before any final UI is built. RUN's dark look and the reveal feed into it. The interface is in English, and TMDB's `en-US` title leads everywhere (#38, #39).

### Engineering

- **Core computations are pure functions over plain data, with the ORM only at the edges.** This covers the objective, knobs, readouts, ripple modes and now playing. It is what keeps the "no silent wrong answer" test suite fast (#25).
- **Server-rendered, little JavaScript, no build step** (#14, #22).
- **No live sync.** Clients tick locally off their own clock and poll every 30–60 s (#13).
- **Judgement values live in the environment, correctness values in source.** Tunable numbers are named constants set from the environment. Correctness settings are hard-coded (#25).
- **No sensitive identifier in a URL path.** Watched-list topics travel in request bodies (#16).
- **Build in vertical slices.** The first deliverable is a deployable slice on the real host. A full end-to-end rehearsal on the real deployment gates inviting the group (#18, #25).

---

## 3. People

| Who | What they are | Can do |
|---|---|---|
| **Voter** | Registered through the **join code**. The roster holds voters and nothing else, so "everyone" always means the whole roster. | Write on two surfaces: SUGGEST and VOTE. Notes stay writable in APPROVE. Otherwise reads whatever the current phase shows. |
| **Admin** | One credential set in an environment variable, outside the roster. Never a voter and never counted as one. | Everything, on surfaces that are never phase-gated: moves the phase, curates, removes voters, resets passwords, solves, arranges, actualises. |
| **Host** | A friend whose Docker homelab runs the stack behind his proxy. | Can read the database by construction. This is named and accepted, not mitigated (#18). |

The dev votes through an ordinary voter registration, with a separate sign-in, and counts in the floor like anyone else (#8).

---

## 4. Workflow

### 4.1 The window

1. **Rebuild.** Build the image locally, push it to the host's registry, and deploy the stack. Set the environment: join code, admin password, API keys, time zone, tuning constants.
2. **Rehearse** end to end on the real deployment, including a restore and a teardown followed by a rebuild. The group is invited only after this passes (#25).
3. **Invite.** The join code goes into the group chat. Voters register themselves: join code → display name → password (#8).
4. **Phases,** SUGGEST → … → RUN, each one moved by the admin (below).
5. **Teardown** after the evening. Remove the containers and both volumes and delete every local copy. Only the stack definition is kept, plus a pseudonymised **score** matrix taken at the reveal for the dev's private testing (#25, #30). No mechanism reminds anyone that teardown is due; it is a habit tied to the anchor date (#16).

### 4.2 Phases

A fresh database starts in SUGGEST. The admin moves the phase one step at a time, in either direction, at any time. The phase decides which voter page is shown. Admin surfaces are never gated by it.

| Phase | Voters | Admin |
|---|---|---|
| **SUGGEST** | Suggest films (picker → pitch), add notes, withdraw their own **suggestions**, correct runtime, set the watched list. | Approves, drops and edits runtime early if they like. |
| **APPROVE** | See the **pool** frozen. Notes stay writable. No admin decisions are shown. | Curates on the approve screen. Runtime is required to approve. |
| **VOTE** | See the **ballot**: score, veto, mark seen it, mark done. No notes. | Watches the done roster. **Approval** stays open, and growing the ballot clears every done marker. |
| **PICK** | See the **reveal**. | Sets the budget and anchor, runs **SOLVE** with **knobs**, compares and keeps proposals, lays a slate onto the timetable and arranges it. |
| **RUN** | See the published evening, with the reveal one link away. | Edits the timetable to keep it true as the evening runs. |

**Effects of each move:**

- **Every move,** in either direction, refreshes DTDD data within the rate limit (§6) and is appended to the **phase history**.
- **VOTE → PICK** is the reveal. It cannot be undone. The confirm step names who isn't done and says the move can't be taken back.
- **PICK → VOTE** hides the scores again. The ballot then carries one line saying scores were open while VOTE was closed. Done markers are kept.
- **PICK → RUN** publishes the timetable and purges the DTDD cache. **RUN → PICK** takes the evening down at once.
- Nothing follows RUN. The marathon ending is a fact about the world, and the app stays in RUN until teardown (#13).

**Phase check.** Every voter action has a window of phases. One server-side check refuses a post from outside its window and reloads the tab into the current phase (#34).

| Action | Window |
|---|---|
| Suggest, write a note | SUGGEST–APPROVE. Suggesting is only offered in SUGGEST; the window just catches stale tabs. |
| Withdraw, runtime pencil | SUGGEST. Only on an unapproved film nothing downstream holds. |
| Score, veto, seen it, done | VOTE |
| Correct the DTDD match | SUGGEST–VOTE (the admin as well) |
| Edit the watched list | Every phase but RUN |

Pages that poll and find the phase moved reload the same way.

### 4.3 What can change, and when

- **Approval** can be undecided, approved or dropped, and can change at any time. Growing the ballot during VOTE clears every done marker, and the confirm step prints the cost ("6 of 9 → 0 of 9"). Shrinking it clears nothing (#15, #28).
- **Drop** destroys nothing and only affects future use. A dropped film leaves the ballot and SOLVE, but the timetable or a kept proposal that already holds it keeps it and keeps counting its scores. Only the admin sees it marked as dropped (#26).
- **Removal** deletes a voter's scores, vetoes, done marker and notes on other films. Their suggestions and pitches stay, marked removed. It is not a ban (#28).
- **Runtime** can be edited by anyone during SUGGEST on a film its suggester could still withdraw, and by the admin alone otherwise. Editing it on the Films tab changes the **box** length without rippling; any overlap is just flagged (#34, #36).

---

## 5. The decision model

### Signals (VOTE)

- **Score:** five coarse steps: +3 top pick, +2 keen, +1 happy, 0 don't mind, −1 rather not. Taken at face value, never normalised. A film left **unsorted** counts as 0. Hidden from other voters until the reveal.
- **Veto:** "I wouldn't be in the room". Bars the film from representing that voter and scores it −2, a reserved step that prices the group losing them. Unlimited and attributed. Others see it during VOTE.
- **Seen it:** bars the film from representing that voter. Does nothing else. Others see it during VOTE.
- **Done:** a public, reversible signal. Never a lock.

### Objective (SOLVE)

For a slate within the budget, compared in strict priority:

1. **Floor:** the lowest **representation** across the floor set.
2. **Σrep:** the sum of representations.
3. **Total:** every score for every film. Only separates slates that tie on 1 and 2.

The budget caps **screen time** and is the only hard constraint. Runtime never appears in the objective, and slack is expected. Variety and order are not modelled; they are the admin's eye in PICK. It is solved as a MILP with HiGHS, in-process, in 25–600 ms (#6, #10, #33).

- **Floor set:** everyone who could be represented above zero. Anyone outside it is named on screen with the reason: *no ballot*, *nothing representable*, or *set aside by knob* (#33).
- **Knobs** (hypotheses that never touch stored votes): without a voter, disregard a voter's vetoes, fix a film in, fix a film out. The settings in force are the **basis** (#17).
- **Batch:** up to five proposals, made real alternatives by the **diversity cut**, extended with "more", and replaced when a knob changes. A short batch is never padded (#17).
- **Shortlist:** proposals the admin keeps, stored as the film set plus its **provenance**, and re-scored live under the current basis (#17).

### Comparing

Every slate on screen (the timetable's own films, the shortlist, the batch) shows its standing and tier, with floor and Σrep shown as the distance from the best. Expanding a slate shows **film points** and whom each film represents, plus each voter's representative and **slate sum**. Ticking any two slates shows the **swap**. Films are listed in **slate order** everywhere (#24, #36).

---

## 6. Trigger warnings

Informational only. They never feed the objective and never veto on anyone's behalf. The link to the objective is a voter choosing to veto (#20).

- **Source:** DoesTheDogDie, keyed by TMDB id. A guarded retry by title and year when the id finds nothing, and a movie-type filter. DTDD returns crowd yes/no counts per **topic**, which are evidence, not verdicts. DTDD's own labels and grouping are used site-wide (#19, #23).
- **Watched list:** the topics a voter wants to be told about. Private, admin included. Disclosed upfront. Opting out takes no surface: tick nothing, or press "I don't care" (#20).
- **What voters see:** **matched topics** with raw counts in the opened card and beside the veto control. On a tile or closed card, the **trigger icon** (amber ring) is the only mark. The icon needs enough yes votes, more than the no votes, to make a claim. Matched films come first in the voter's Unsorted tray (#35, #38).
- **Admin surfaces** show a film's DTDD data, match field and topic list, and nothing personal.
- **Gaps are named, never shown as an all-clear.** A film is **uncovered** when DTDD has no evidence for it, and **not fetched** when DTDD hasn't answered. Notes cover whatever the crowd evidence misses.
- **Snapshots** are stored, because the rate limit (30 requests a minute) forbids live fetching. Each phase move refreshes the vocabulary, then films oldest-first until the rate limit's floor or 20 s. The move never waits on it. Films not fetched go first next time, and a failed refresh keeps the old snapshot. Everything is purged on entering RUN (#32).
- **Match correction:** one paste-a-link control, open to any voter and the admin through VOTE. It is tagged `auto` or `set by <name>`.
- **Obligations:** a "Powered by DoesTheDogDie.com" link on every view that shows DTDD data, a public privacy policy, and an abuse contact (#5, #16).

Nothing about trigger warnings appears in PICK or RUN: by then they have already been acted on as vetoes.

---

## 7. Arranging and running

- **Timetable:** one per marathon, never versioned, never touched by solving. Its **boxes** are film boxes, fixed at their runtime, and **labelled boxes** (meals, breaks) that can be resized and marked **flexible**. Each box is an offset in elapsed minutes from the anchor, an instant shown in the deployment's one time zone. The minutes between boxes are just empty (#12, #36).
- **Use this slate:** the only path from a proposal to the timetable. It replaces everything, lays films back to back from the anchor in slate order, is always shown armed with a preview, and is unavailable until the anchor is set (#36).
- **Editing:** boxes are dragged and snap to neighbours and a 5-minute grid. The sticky **ripple mode** decides what an edit does to boxes it comes to overlap: leave them (the default), **push** keeping gaps, or push keeping the end time. The same tool serves PICK and RUN. Arrange utilities ignore the mode. The server computes every change and previews it live (#13, #22).
- **Readouts:** **set readouts** (floor, representatives, Σrep, screen time against the budget, floor set size, vetoes) and **arrangement readouts** (presence strips, shown only for voters not present throughout, and **shared time**), plus **elapsed time**, named apart from screen time. Admin only (#12).
- **RUN:** advancing publishes the timetable, possibly days ahead. The voter's evening fits top to bottom on one phone screen. Past boxes are dimmed and now playing is shown inside the playing box; in a gap or before the start, the next box reads as next. It has no readouts and no card, and no separate mode before the evening. Actualising runs from a laptop on the same editor (#13, #22).

---

## 8. Surfaces

### Public (outside the login wall, no database)

- **Privacy policy:** rendered from a file in the public repo (#16).
- **Login** and **registration** (join code → display name → password). Login errors never say whether the name or the password was wrong. Repeated failures get a timed backoff, never a lockout (#16, #31).

### Voter side

**Shell** (#27, #37):
- **Header:** the phase page, *My warnings* (every phase but RUN), and the voter's name opening *Change password* and *Log out*.
- **Nag bar:** shown until the reveal, and only until the voter ticks a topic or presses "I don't care".
- **Footer:** TMDB attribution, DTDD link, abuse `mailto:`, privacy policy.

The page *is* the phase: one page per phase, no hub, no tabs.

| Surface | Contents |
|---|---|
| **Welcome** | Shown once after registration, never linked again. Rough points, then two exits that depend on the phase: set up warnings, or go suggest (#23). |
| **Forced password change** | After an admin reset (#28). |
| **My warnings** (trigger list page) | One scrolling page in DTDD's grouping. Privacy disclosure and "I don't care" at the top, live search, ticked topics as chips. Every topic names the films carrying it: the pool through APPROVE, the ballot from VOTE (#23, #35). |
| **SUGGEST** | A *Suggest a film* panel above the pool. Find, with a trailing year to narrow → picker of five poster tiles, never auto-advanced, films already in the pool marked → pitch box, with runtime on one line and a pencil. *Add it by hand* for anything TMDB can't find, and a message beside it during a TMDB outage. The pool lists film cards with a *Mine* filter (#21, #27). |
| **APPROVE** | The same pool, frozen. Notes still writable. |
| **VOTE** (ballot) | See below. |
| **PICK** (reveal) | See below. |
| **RUN** | The evening (§7), with the reveal one header link away. |

**VOTE** (#9, #35):
- **Header:** `n of N scored`, the done roster by name, and the *I'm done* toggle.
- **Ballot:** a sticky Unsorted tray, then five colour bands (+3 … −1) and a separate dashed-red Veto band. Dropping a tile into a band is the score.
- **Veto band:** a tile dropped there widens to show matched topics and a reason box.
- **Tiles:** poster, title and year only. Their state is on the frame: amber ring for a match, greyed for seen it, a red ribbon with initials for vetoes by others.
- **Opening a tile:** the film card expands in place inside its band, with others' veto reasons and seen-it flags shown one line each.

**Reveal** (#29):
- A matrix: one row per film, one column per voter, scores in the cells, a points column on the right.
- Sorted by points. Clicking a name re-sorts by that voter's ballot.
- A blank is a blank, a voter who never scored shows as *didn't vote*, vetoes are ☒ and seen it is a badge.
- The film card opens inline under its row, read-only.
- The floor set is not mentioned here; it is the admin's readout.

### Admin console

**Shell:** four tabs (**Phase · Films · Pick · Roster**) under a header with the line *Voter side ↗ · signed in there as …* and *Log out*. The console opens on the tab for the current phase and stays put when the phase moves. There is no Django admin; break-glass is shell access on the host (#16, #28).

| Tab | Contents |
|---|---|
| **Phase** | The phase track with dates from the phase history. Both possible moves, each with its consequences printed. Click, then an inline confirm. |
| **Films** (approve screen) | Ledger rows: runtime box, a flag when it differs from TMDB, DTDD status, *Approve* / *Drop*. The title opens the film card inline. One quiet line lists films with stale or unfetched DTDD data. |
| **Pick** | Budget and anchor in a header above two sub-tabs. **Compare:** knobs, solve and "more", the ledger (timetable row, shortlist, batch), the floor set line, keep, swap, *Use this slate*. **Timetable:** the **track**, ripple mode, arrange utilities, readouts, the selected box, the candidate list for adding films by hand, and the shortlist rows (#22, #24). |
| **Roster** | View, remove, reset password (shown once, forces a change at next login). The floor set line is always shown. |

### Shared components

- **Film card:** one component for SUGGEST, APPROVE, VOTE and the reveal; only its **phase bar** changes. Collapsed and expanded contents are as defined in the glossary.
- **Title card:** stands in for a missing poster anywhere a poster appears (#38).
- **Slate ledger row:** used in Compare and in the Timetable tab's shortlist.
- **Box:** one model and box component behind both the admin's track and the voter's RUN evening, in two different layouts.

---

## 9. Modules

| Module | Responsibility |
|---|---|
| **Identity and access** | Registration through the join code (a 24-character random string). Display names unique regardless of case, 1–20 characters, never renamed. Password login with sessions that outlive the window. Admin authentication from the environment, kept separate. Login backoff. Password change and reset. Removal (#8, #16, #37). |
| **Phase** | Phase derived from the phase history. One step at a time, both directions. The phase check. What each move triggers: DTDD refresh, RUN purge, reveal state. |
| **Films and metadata** | TMDB search (debounced) and one detail fetch per film, never refreshed. Manual entry. One suggestion per TMDB id. Runtime with its source. Title card. |
| **Suggestions, notes, approval** | Suggest and withdraw. One note per voter per film, the suggester's being the pitch. Approval states and the done-marker rule. |
| **Ballot** | Score, veto with reason, seen it, done. Per-voter Unsorted order: matched films first, then the rest, in a stable per-voter shuffle. |
| **Trigger warnings** | DTDD matching and correction, snapshots and vocabulary, refresh scheduling against the live rate limit, watched lists, matched topics, icon threshold, purge. |
| **Solver** | Floor set, objective, knobs, batch with diversity cut, the solver's own reasons for a short batch. Pure function over plain data. |
| **Readouts** | Standing, tier, swap, film points, slate sum, slate order, set readouts. Shared by Compare and Timetable. |
| **Timetable engine** | Boxes, anchor, ripple modes and push, flexible squeeze, arrange utilities, preview, overlap, presence strips, shared time, elapsed time, now playing. Pure, and computed on the server. |
| **Reveal** | The score matrix, sorts, and the reopened-VOTE line read from the phase history. |
| **Operations** | One container behind the host's proxy. SQLite on a volume. A backup sidecar taking 7 nightly snapshots, with a row-count check. Configuration only through the environment. Teardown. The app trusts only the forwarded-protocol header from the proxy. HSTS. Access logs without client addresses (#16, #18, #30, #31). |

**Stored vs derived.** The database stores only what is true in every phase: voters, suggestions with their film metadata, runtime and approval, notes, ballot entries, done markers, watched lists, DTDD snapshots and vocabulary, phase history, the timetable (anchor, budget, boxes) and the shortlist. Everything else is computed from it on demand: the phase, the reveal state, the candidates, the floor set, standings, readouts and now playing (#26).

---

## 10. Deliberately absent

Each was considered and ruled out. Returning one needs a new decision.

- **Date-finding and attendance.** No availability or presence model, and no clock-time question to voters. Presence-aware PICK is worked out in [`docs/deferred/presence-aware-picking.md`](deferred/presence-aware-picking.md) and returns only if displaced representatives turn out to be common (#11).
- **Automation and channels.** No scheduler, deadlines, email, notifications, push, live sync, share link, export or public view (#12, #13, #15).
- **Extra state.** No undo, drafts or timetable versions. No planned-vs-actual record. Nothing after RUN: no ratings, no archive (#13, #39).
- **Multiple marathons.** No Marathon entity, no selector, nothing carried between windows (#15).
- **Hardcoded referees.** No approval queue, no veto caps, no login lockout, no admin-as-voter flag, no Django admin (#8, #10, #16).
- **Official metadata and extras.** No official synopsis or genres, no genre-mix readout, no embedded trailer, no admin poster link, no translation (#21, #24, #38).
- **Visibility.** No display of how far a voter has got during VOTE beyond done. No aggregate of watched lists for anyone (#15, #20).
- **Edge-case surfaces.** No renaming, no TV-series search (*Add it by hand* covers it), no admin backup button (#15, #18, #37).

**Accepted risks**, named rather than solved:
- Reopening VOTE leaves some voters having seen scores, so the re-vote is unevenly anchored.
- The host can read the votes.
- A voter whose real-world plans make them miss a film they scored highly is left to the admin's eye.
- The join code is the perimeter, and it lives in a group chat.
- The host's proxy logs outlive teardown.
