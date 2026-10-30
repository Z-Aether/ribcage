# Ribcage — milestones

The big-picture build schedule: ten milestones, each a vertical slice that is reviewed and approved by the dev before the next one starts. Read alongside [`design.md`](design.md), which says *what* is built; this says *in what order*.

- Terms are used as defined in [`GLOSSARY.md`](../GLOSSARY.md). Ticket numbers (#n) point at the decision of record.
- Where this doc and a ticket or `design.md` disagree, the newest of them wins; flag the conflict.
- Each milestone's parent ticket is in the table below. A milestone's section here is the condensed scope; its parent carries the detail, as a baseline until the milestone's breakdown reviews it.

---

## How a milestone runs

- **Size.** About 20 implementation tickets, each one agent session and itself a vertical slice (model → endpoint → template → test). One orchestrator session implements, reviews and tests a whole milestone.
- **Gate.** A milestone ends tested locally, then the dev tests it by hand and approves it. Nothing in the next milestone starts before that.
- **The host only where it is what's tested.** A milestone carries a host step only for a change the host itself must prove, such as the proxy, the network or the volumes, and that step blocks nothing it doesn't gate. The dev may redeploy at any gate; it is never required (#61).
- **Deployable at every gate.** Every milestone leaves the app in a state that would run end to end on the real host. Unbuilt phase pages are placeholders, never broken pages.
- **Cross-cutting work grows with its owner.** Each milestone extends these as its entities and actions arrive, rather than leaving them to the end:
  - the **phase check**: one window per new voter action (#34);
  - **removal**: what a removed voter's new data does (#28);
  - **phase-move effects**: each added by the milestone that owns it (DTDD refresh, reveal, RUN purge);
  - the **seed command**: reaches the milestone's state locally, for Playwright and for the dev's review;
  - the **pure-function suite**, the **trap catalogue** and the **invariant tests** (#25).
- **Copy.** Its substance is settled; final wording is written as each surface is built, with one pass in M10 (#39).

### At a glance

| # | Milestone | Ships | Tickets | Parent |
|---|---|---|---|---|
| M1 | Walking skeleton on the real host | Hello World, deployed, backed up, restorable | ~14 | #42 |
| M2 | Theme and component kit | The one theme, the shared poster and film card on fixture data | 3 | #56 |
| M3 | Identity, phases and the two shells | Register, log in, roster, phase moves, empty phase pages | 15 | #60 |
| M4 | SUGGEST and APPROVE | The pool, suggested by voters and curated by the admin | ~20 | #61 |
| M5 | Trigger warnings | DTDD data, watched lists, matched topics | ~18 | #62 |
| M6 | VOTE | The ballot, done markers, approval during VOTE | 8 | #63 |
| M7 | The timetable, without SOLVE | PICK's Timetable tab, hand-built slates, readouts | ~20 | #64 |
| M8 | The reveal and the evening | Reveal, RUN, publishing | ~15 | #65 |
| M9 | SOLVE and Compare | The solver, knobs, batch, shortlist, Compare tab | ~20 | #66 |
| M10 | Rehearsal and launch | The gating end-to-end rehearsal on the real deployment | ~12 | #67 |

```
M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10
                 │              │         │    │
                 pool exists    votes     a full marathon
                                exist     without the solver
```

---

## M1 — Walking skeleton on the real host

**Why first.** The host's proxy, TLS, DNS and network can't be reproduced locally, so every deployment unknown is settled before feature work (#18). The CSRF trap behind the proxy is invisible to localhost (#16, #25).

**Scope**
- Django 6.1 project on Python 3.14, the custom `Voter` user model in place from the first migration (#26), settings read only from the environment, judgement constants as named env-set values (#25).
- A Hello World page plus one form POST, so CSRF and HTTPS are proven through the real proxy (#31).
- HSTS, access logs without client addresses, reading nothing the proxy forwards (#16, #31, #54).
- Image: gunicorn, WhiteNoise, vendored static files, an allowlist `.dockerignore`, a pinned tag. Built locally, pushed to the GitLab registry, run as a Komodo stack (#40).
- SQLite on a volume. Backup sidecar taking a backup each night and keeping the 7 newest; the automated row-count test (#25, #30).
- The public privacy policy page, rendered from its file (#16). Wording is finished in M10.
- Test harness: pytest for the pure suite and HTTP tests, Playwright over MCP against a seeded local instance, a seed command skeleton (#25).
- Written runbook for rebuild, restore and teardown.

**Deployable state:** a Hello World on the real subdomain, with backups.

**Dev's review:** open it from outside the network. Submit the form. Restore a backup into a fresh stack. Tear the stack down and rebuild it.

---

## M2 — Theme and component kit

**Why here.** One theme must be settled before any final UI is built (#39), and the first voter-facing pages (login, registration) arrive in M3. The prototype branches are the inputs.

**Scope** (#56)
- The one full fetch of TMDB and DTDD payloads for the fifty seed films, stored in `fixtures/films/` for offline use (#25, #40).
- The theme: tokens over the vendored classless base. The voter skin is rounded and roomy, the admin skin is dense ledgers, and RUN is dark (#29, #39). It fixes the state colours later surfaces share: the score scale, the veto, the ring, seen it (#58).
- Only the components more than one surface shares, as templates over plain data, so later milestones only bind models to them:
  - the **poster** slot, with the **title card** for posterless films (#38);
  - the **film card**, collapsed and expanded, with an empty slot for each phase bar (#21).
- A dev-only **gallery** route that shows the theme and these components on fixture films. It stays as the visual reference for later reviews, and later milestones add their components to it.
- A component serving one view is designed in that view's milestone: phase bars in M4, M6 and M8, the card's DTDD section in M5, tiles in M6, the box in M7 and M8, the reveal cells in M8, the slate ledger row in M9.

**Deployable state:** unchanged app, now themed, plus the gallery locally.

**Dev's review:** the theme, the poster and the film card in the gallery, against the prototypes. This is the gate where "intuitive or out" is cheapest to apply.

---

## M3 — Identity, phases and the two shells

**Why here.** Every later surface hangs off a logged-in voter, the admin console, and the phase that decides which voter page is shown. The phase module is a foundation, not a feature.

**Scope**
- **Identity:** registration through the join code (the code, then display name and password), display-name rules, login with the generic error and timed backoff, ~60-day sessions, log out, change password (#8, #16, #31, #37, #60).
- **Admin:** a password-only login against the environment credential, with a separate session cookie held alongside a voter session, and the same backoff and session length (#8, #60).
- **Roster tab:** view, remove (the routine, extended by later milestones), reset password shown once with a forced change at next login (#28).
- **Phase:** phase history, the derived phase, one step in either direction. The Phase tab shows the track with dates, both moves with their consequences, and click then inline confirm (#15, #28).
- **Phase check:** one server-side mechanism that refuses a post from outside its window and reloads the tab into the current phase. Polling pages reload the same way, and no voter page polls before RUN (#34, #60).
- **Voter shell:** header (phase page, name menu; public pages the wordmark alone, #83), footer (attributions, abuse `mailto:`, privacy policy), Welcome shown once (replaced by the permanent *How it works* page, #134, #63), placeholder pages for all five phases (#23, #27, #37), and Back and Forward showing every page as it is now (#84). Its *Set up my warnings* button waits for M5 (#60).
- **Admin shell:** the five tabs, Backup the fifth after Roster (#86), opening on the current phase's tab, with the *Voter side ↗ · signed in there as …* line (#28), and Back and Forward showing every tab as it is now (#84).
- **Backup download and upload:** the Backup tab, a page that serves a backup for a one-time code created in the container's terminal, and takes one back onto the host the same way for a restore, replacing the runbook's copy-paste routes in both directions (#54, #55, #68, #81, #86).

**Deployable state:** people can register and log in, the admin can remove people and move phases, and each phase shows an empty page.

**Dev's review:** register several voters, log in as admin and voter at once, reset and force a change, remove a voter, walk the phases both ways with a stale tab open (it lands on the current phase at its next click).

---

## M4 — SUGGEST and APPROVE

**Why here.** The first slice where the app does its job. Admin approval is included because the ballot is the approved set: VOTE can't be tested without it.

**Scope**
- **TMDB:** debounced search with a trailing year, one detail fetch per film, never refreshed. The outage message (#5, #21).
- **Suggest a film:** find → picker of five poster tiles, never auto-advanced, pool films marked → pitch box with runtime and its pencil. *Add it by hand* (#21, #27).
- **The pool:** film cards with the SUGGEST phase bar, the *Mine* filter, notes (one per voter per film, the pitch being the suggester's), withdraw (#21, #26).
- **APPROVE page:** the same pool, frozen, notes still writable.
- **Films tab:** ledger rows with runtime box and TMDB-differs flag, *Approve* / *Drop*, runtime required to approve, title opening the card inline (#28).
- Phase windows for suggest, note, withdraw and the runtime pencil (#34). Removal now leaves suggestions and pitches marked removed and deletes notes on other films (#28).

**Deployable state:** a group could suggest films and the admin could curate them.

**Dev's review:** suggest real films, including an ambiguous title, a TV series by hand and a disputed runtime. Withdraw, approve, drop, move SUGGEST ↔ APPROVE.

---

## M5 — Trigger warnings

**Why here.** The ballot is built on it: the Unsorted tray puts matched films first and the veto band shows matched topics (#9, #35). Building it before VOTE means the ballot is built once.

**Scope**
- **DTDD client:** lookup by TMDB id, the guarded retry by title and year, the movie-type filter (#19, #23).
- **Snapshots and vocabulary:** stored per film. Every phase move refreshes the vocabulary, then films oldest-first, within the rate limit's floor or 20 s, never blocking the move; a failed refresh keeps the old snapshot, and a record gone from DTDD skips only its film (#32, #104).
- **The RUN purge:** entering RUN deletes every snapshot and the vocabulary, and leaving it fetches them again. Moved here from M8, since M5 owns the snapshots (#32, #62).
- **Match correction:** the paste-a-link control, previewed before it is saved, tagged `auto` or `set by <name>`, windowed SUGGEST–VOTE for voters and never for the admin (#32, #34, #62, #78).
- **My warnings:** the scrolling page in DTDD's grouping, privacy disclosure, *I don't care*, live search, chips, carrying films per topic. The nag bar. Topics travel in request bodies (#16, #20, #23).
- **On the card:** matched topics with raw counts (the full list drops topics with no yes vote, #103), the trigger icon and its threshold, *uncovered* and *not fetched* named as gaps (#35). Each row of the full list carries a quiet *watch* toggle, the same write as the page (#114).
- **Films tab:** DTDD status per row and the quiet stale-or-unfetched line (#28).
- The "Powered by DoesTheDogDie.com" invariant test and the watched-list privacy invariant test (#25).

**Deployable state:** the pool carries trigger data and voters can set their watched list.

**Dev's review:** tick topics and see the matching films ringed. Correct a wrong match. Move phases and watch the refresh fill in, and RUN's purge and refetch. Confirm the admin sees no personal data. The DoesTheDogDie check from the host blocks nothing (#62).

---

## M6 — VOTE

**Scope**
- **Ballot:** one record per voter and film. Score, veto, seen it, done, each windowed to VOTE; a veto's reason is the voter's note (#9, #26, #34, #128).
- **The ballot page:** the header (`n of N scored`, done roster, *I'm done*), the sticky Unsorted tray in its per-voter order, the five bands, the dashed-red Veto band, which holds the same collapsed tiles as any band, and a drop into it with no note opens the card with the note box focused; notes are written in VOTE as in SUGGEST and APPROVE (#9, #35, #38, #120, #128, #150).
- **Tiles:** frame states, opening the card in place with vetoers' notes marked, a bare line for a vetoer with none, and seen-it flags (#35, #128).
- **The admin's side of VOTE:** approval staying open, growing the ballot clearing every done marker with its cost in the confirm ("6 of 9 → 0 of 9"), shrinking clearing nothing. The done count on the Films and Phase tabs, and the Roster's *Scored*, *Vetoes* and *Done* columns (#15, #28, #63).
- **Moves:** the VOTE → PICK confirm naming who isn't done and saying it can't be undone. PICK → VOTE keeps done markers and adds the reopened-VOTE line to the ballot (#15, #34).
- Removal now deletes the voter's scores, vetoes, seen-it flags and done marker.

**Deployable state:** a group could vote. The PICK page is still a placeholder.

**Dev's review:** vote as several voters, including one who never votes. Veto with a reason, approve a film mid-VOTE, close and reopen VOTE.

---

## M7 — The timetable, without SOLVE

**Why before SOLVE.** The timetable is the largest single piece and the riskiest UI (#22, #25), and a hand-built slate is a complete answer on its own. SOLVE then only adds a better way to fill it.

**Scope**
- **PICK header:** budget and anchor, above the two sub-tabs (#24).
- **Timetable engine,** pure and on the server: boxes as offsets from the anchor, snapping to neighbours and the 5-minute grid, overlap, the three ripple modes, flexible squeeze, the two arrange utilities by arming, elapsed time (#12, #13, #22, #36).
- **Track:** fitted to the window, custom pointer dragging with the server-computed live preview morphed in, the ripple mode control, the selected box, labelled boxes (#22).
- **Candidate list** for adding films to the timetable by hand.
- **Readouts:** the floor set, representatives, floor, Σrep, screen time against the budget, vetoes, presence strips, shared time (#12, #33). Film points and slate sums for the timetable's own slate.
- Runtime edits on the Films tab change box length without rippling. Dropped films stay on the timetable, marked for the admin (#26, #36).
- The floor set line on the Roster tab.

**Deployable state:** the admin can build and arrange a full evening by hand.

**Dev's review:** build an evening from seeded votes. Drag through each ripple mode, arm both utilities, go over budget, drop a film that's on the timetable.

---

## M8 — The reveal and the evening

**Scope**
- **The reveal:** the matrix, sort by points or by a voter's ballot, *didn't vote*, ☒ and the seen-it badge, the read-only card opening under its row (#29).
- **PICK → RUN:** publishes the timetable. **RUN → PICK** takes the evening down at once. The same moves' DTDD purge and refetch are M5's (#13, #32, #62).
- **The RUN page:** the vertical evening fitted to one phone screen, past boxes dimmed, now playing inside the playing box, next box in a gap or before the start, the 30–60 s poll, the reveal one header link away (#13, #22, #36).
- **Actualising:** the M7 editor used in RUN.
- Every voter page's RUN-specific behaviour: *My warnings* gone from the name menu, the watched-list window closing (#34).
- The RUN page tested on real phones, since a broken RUN is unfixable at any price (#25).

**Deployable state: a complete marathon, start to finish, without the solver.** This is the earliest point the app could serve a real marathon.

**Dev's review:** run a whole marathon on the seed data with the anchor in the past and in the future. Actualise from a laptop while watching on a phone.

---

## M9 — SOLVE and Compare

**Scope**
- **The objective,** pure over plain data: floor set with its reasons, integerised `K·(W·m + Σrep) + T` with `K` per solve, `highspy` pinned `>= 1.15.1`, `mip_rel_gap = 0` (#6, #10, #33).
- **Knobs and the basis:** without a voter, disregard a voter's vetoes, fix a film in or out (#17).
- **The batch:** up to five proposals through the diversity cut, "more", replacement on a knob change, the solver's own reasons for a short batch. Remeasure `k = 4` on the seed corpus and fall back to `k = 2` if it bites (#17).
- **Compare tab:** knobs, solve and "more", the ledger (timetable row, shortlist, batch), standing and tier, the floor set line, keep, swap, *Use this slate* armed with a preview and unavailable without an anchor (#24, #36).
- **The shortlist:** film set plus provenance, re-scored live under the current basis, its rows also in the Timetable tab (#17, #22).
- **Tests:** #6's enumeration oracle as a marked test and a generator of hard-coded fixtures. The trap catalogue's solver traps (#25).
- Tuning stage two on the seed corpus (#25).

**Deployable state:** feature complete.

**Dev's review:** solve the seed votes and check the batch against the dev's own judgement. Try every knob. Keep, swap, use a slate, then rearrange it.

---

## M10 — Rehearsal and launch

**Why last.** The rehearsal is the real deliverable and the gate on inviting the group (#25).

**Scope**
- A copy pass over every surface, and the final privacy policy (#16, #39).
- A review of the trap catalogue and invariant tests against `design.md`.
- The pseudonymised score-matrix extraction, scripted for shell access at the reveal (#25, #30).
- **The rehearsal on the real deployment:** ten concurrent identities through every phase, RUN with the anchor in the past, a live restore, then a teardown followed by a rebuild (#25, #30).
- Fixes found by the rehearsal.

**Deployable state:** ready to invite the group.

**Dev's review:** the rehearsal itself.
