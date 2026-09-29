# Ribcage

A web app for a fixed group of friends to agree on a slate of films for a marathon within a time budget, then arrange and run the evening. It is stood up for one marathon and torn down after, not kept running between them. Each term names the ticket that fixed it.

## Language

### Lifecycle

**Marathon**:
The single event one running copy of the app exists to plan and run. Nothing carries from one to the next, and the app never names, numbers or selects one. (#8, #15)
_Avoid_: event, session, edition, instance

**Window**:
The span of a few weeks in which one marathon is organised and run, from the app being rebuilt and wiped to its being stopped. About three a year, with nothing crossing between them. (#7, #18)
_Avoid_: season, cycle, iteration

**Teardown**:
The end of a window: the app is stopped and unreachable, and nothing it held is kept. The routine end of every marathon, including one abandoned partway. (#7, #15, #18)
_Avoid_: archive, cancel, shutdown

**Phase**:
Which of five stages the marathon is in: SUGGEST, APPROVE, VOTE, PICK, RUN. It decides which of the two user-writable surfaces, SUGGEST and VOTE, is live; it never gates the admin and moves one step at a time in either direction. A fresh database starts in SUGGEST — there is no phase before it, because standing the app up is the deployment's business, not a state the app is in. (#15, #28)
_Avoid_: stage, step, status, state; SETUP (dropped as a phase 2026-09-12)

**Phase history**:
The append-only record of every phase move and when it was made. Whether the reveal has ever happened is read from it, never kept as a flag of its own. (#28, #29)
_Avoid_: audit log, previous phase

### People

**Voter**:
A person registered into the marathon. The roster holds voters and nothing else, so "everyone" always means the whole roster. (#8)
_Avoid_: user, account, member, participant

**Admin**:
The person who runs the marathon and moves its phase, signing in with a credential that lives outside the roster. Never a voter and never counted as one; the person holding it may also register as a voter, under a separate sign-in. (#8, #28)
_Avoid_: owner, host, organiser, moderator

**Join code**:
The one shared secret that admits a person to registration. Used exactly once per person; a gate, never a login credential. (#8)
_Avoid_: invite code, invite link, access code

**Display name**:
The unique name a voter chooses at registration and is known by everywhere. The only personal detail the app holds. (#8)
_Avoid_: username, handle, real name

**Roster**:
The list of everyone registered for the marathon. The control over who is in: looked at by the admin and removed from after the fact, never approved into. (#8, #28)
_Avoid_: user list, membership, directory

**Removal**:
The admin taking a voter off the roster. Their scores, vetoes, done marker and notes on other films go with them; their suggestions stay, pitch and place on the ballot included, still attributed to them and marked removed. Not a ban: the join code still admits them. (#8, #28)
_Avoid_: delete, ban, kick, prune

**Attribution**:
The binding of every suggestion, score and veto to the voter who made it. A property of the model rather than of any screen, so "anonymous" can only ever mean hidden from other voters. (#8, #10)
_Avoid_: anonymity (as a claim about the app), authorship

**Reveal**:
The moment VOTE closes and every voter's scores become visible, per person, to the whole group. One-way: reopening VOTE hides the scores again but cannot unsee them. (#8, #15, #29)
_Avoid_: publish (that is what advancing to RUN does to the timetable), results

### Suggesting

**Suggestion**:
A film a voter puts forward in SUGGEST, attributed to them and carrying the admin's approval. Made and withdrawn in SUGGEST only; a withdrawn suggestion is simply gone, while one whose suggester is removed stays. (#8, #15, #27, #28)
_Avoid_: nomination, entry, submission

**Pool**:
All the suggestions, whatever their approval. Open to additions in SUGGEST, frozen in APPROVE, and not shown to voters from VOTE on, when the ballot takes its place; voters never see approval, and what the admin dropped is only absent from the ballot. (#15, #27, #28)
_Avoid_: queue, backlog, candidate pool

**Approval**:
The admin's standing decision on a suggestion: undecided, approved or dropped. Every suggestion starts undecided, only approved ones are on the ballot, and any of the three can become another at any time. (#15, #28)
_Avoid_: pending, review, status, accept

**Drop**:
The admin's decision to keep a suggestion off the ballot. Reversible and destroys nothing: a dropped film keeps its notes, and any scores and vetoes it gathered as a candidate, unshown and counted nowhere until it is approved again. (#27, #28)
_Avoid_: reject, delete, remove (that is done to a voter), withdraw (that is the suggester's own)

**Picker**:
The step in SUGGEST where the suggester says which film they meant: five poster tiles, never auto-advanced, narrowed by a year typed after the title. Identity is always chosen by a person, never taken from search ranking. (#5, #19, #21)
_Avoid_: autocomplete, search results, disambiguator

**Runtime**:
The length of the particular copy of a film the group will watch, not a fact about the film. Filled in from metadata and editable by anyone during SUGGEST, by the admin after it; the approve screen flags a value that differs from the fetched one. (#5, #12, #15, #19, #21, #27, #28)
_Avoid_: length, duration, official runtime

**Note**:
A voter's own words on a film: one per voter per film, visible to the whole group, editable only by its author and only in SUGGEST and APPROVE. The suggester's note is their **pitch**, shown first, and it outlives their removal; their notes on other films do not. With scores hidden during VOTE, the only channel for persuading the group; also where anything the crowd evidence misses is written down. (#8, #9, #20, #21, #27, #28)
_Avoid_: comment, blurb, description, personal note, freeform note, group note

**Film card**:
The one component that shows a film, shared by SUGGEST, APPROVE and VOTE. Collapsed it shows poster, trigger icon, title, year, director, certificate, trailer and TMDB links, runtime, suggester and every note trimmed; expanded it adds the full notes, the DoesTheDogDie match, matched topics, the topic list and one credit line. Never shows an official synopsis or genres. VOTE and RUN may show it as a sheet instead. (#20, #21)
_Avoid_: movie card, film sheet (as a distinct thing), tile (that is a picker result)

### Voting

**Candidate**:
A suggestion the admin has approved and not since dropped. The candidates are what VOTE and SOLVE work on; a film without a runtime cannot become one. (#5, #15, #28)
_Avoid_: movie; not interchangeable with suggestion, which also covers undecided and dropped films

**Ballot**:
The candidates put before voters in VOTE: exactly the approved suggestions. Growing it once VOTE has opened clears every voter's done marker; shrinking it clears nothing. (#15, #28)
_Avoid_: candidate set, voting list

**Score**:
A voter's stated appetite for a candidate on a coarse five-point scale from "rather not" to "top pick", taken at face value and never normalised against anyone else's. Hidden from other voters until the reveal. A score on a dropped film is kept but counts nowhere while it stays dropped. (#8, #10, #28)
_Avoid_: rating, preference, vote, points

**Veto**:
A voter's declaration that they would not be in the room for a film. It bars the film from representing them and scores it −2 for them, a reserved step below anything hand-entered that prices the group's loss of them; uncapped, attributed and visible while VOTE is open. (#10, #12)
_Avoid_: hard veto, ban, block, exclusion

**Seen it**:
A voter's flag that a candidate could not count as something they wanted from the night. It bars the film from representing them and does nothing else. (#10)
_Avoid_: watched, rewatch penalty

**Absence**:
A voter being out of the room for a film. Only the absence a veto declares is modelled and priced; absence the outside world imposes is never entered, and no voter is ever asked about clock time. (#10, #11)
_Avoid_: attendance, availability, presence (as a modelled thing)

**Done**:
A voter's own signal that they have finished with the current ballot, shown by name to the whole group. Reversible and never a lock on their votes; cleared for everyone when the ballot grows, never when it shrinks or VOTE reopens. (#15, #28)
_Avoid_: submit, lock, finalize, finished

### Selection

**Slate**:
A set of candidates considered together as one evening's films. A set, not an order; SOLVE never proposes one over budget, but the admin may hand-build one that is. (#10, #12)
_Avoid_: lineup, programme, schedule

**Screen time**:
The sum of the runtimes of the films in a slate. The only duration SOLVE knows and the quantity the budget caps. (#6, #10, #12)
_Avoid_: elapsed time (a different number), total runtime, duration

**Budget**:
The admin-set limit on a slate's screen time and SOLVE's only hard constraint; in PICK it is a marker the admin may cross, not a gate. Never a wall-clock cap and never a target: slack is expected. (#6, #10, #12)

**Representative**:
The film in a slate that stands for a voter: their best-scored film there that they have neither vetoed nor seen. When two tie, which one counts is arbitrary. (#10, #17)
_Avoid_: top pick, favourite

**Representation**:
A voter's score for their representative in a slate; zero if they have none. The **floor** is the lowest representation across the floor set, and **Σrep** the sum across it. (#10)
_Avoid_: satisfaction, happiness

**Total**:
The sum of every voter's score for every film in a slate. The objective's least component: it separates slates equal on floor and Σrep and can never outweigh either. (#6, #10)
_Avoid_: ε, tie-break, tiebreaker

**Floor set**:
The voters the floor is computed over: everyone with at least one score on a candidate, never everyone registered, minus anyone set aside by the without-a-voter knob. (#8, #15, #17, #28)

### Proposing

**SOLVE**:
The computation that turns the current ballot, votes and knobs into a batch of proposals. Machinery PICK invokes and re-invokes; never a phase. (#6, #11, #15)
_Avoid_: solve phase, solver run

**Proposal**:
A slate SOLVE hands the admin as one alternative in a batch. Immutable and never edited in place. (#17)
_Avoid_: solution, result, option

**Batch**:
The proposals produced by one solve under one set of knobs: at most five, extended by "more", replaced when a knob changes. Ephemeral, and short when the space is short, never padded. (#17)

**Diversity cut**:
The rule that makes each proposal in a batch a real alternative: it must differ from every other by at least a set number of films, additions and drops counted together. (#6, #17)
_Avoid_: variety, k

**Knob**:
An admin-side hypothesis for one solve, fixing one variable: without a voter, disregard a voter's vetoes, fix a film in, fix a film out. Never touches stored votes. (#11, #12, #17)
_Avoid_: filter, setting, what-if (as a noun)

**Basis**:
The knob settings currently in force, under which every slate on screen is scored. (#17)

**Provenance**:
The knob settings a kept proposal was found under. Explains where it came from; does not score it. (#17)

**Shortlist**:
The proposals the admin has kept. The only stored thing on the PICK surface besides the timetable. (#17)
_Avoid_: saved, favourites, pinned (pinning is a film-level knob)

**Standing**:
A proposal's distance from the best slate on screen in the objective's own components under the current basis: floor and Σrep, with total subordinate. Computed for the timetable's own film set alike, so a hand-edited slate stays comparable. (#12, #17)
_Avoid_: rank, score

**Tier**:
A group of proposals equal on floor and Σrep. Shown as tied, never ranked within; the primary standing the comparison displays. (#17, #24)

**Swap**:
The difference between two slates read as one move: the films out, the films in, and what it does to each voter's representative, score and slate sum. Any two slates on screen can be read as a swap. (#24)
_Avoid_: diff, comparison (as a noun for this), delta

**Film points**:
Everyone's score for one film in a slate, summed, with a veto counting as its −2. The total's own per-film share; says what a film carries and is never fed back into the objective. (#6, #24)
_Avoid_: load, weight, popularity

**Slate sum**:
One voter's scores for every film in a slate, summed. How the whole evening reads for them, beside the single representative that the objective sees. (#24)
_Avoid_: personal total, satisfaction

### Arranging

**Timetable**:
The single arrangement of boxes against the anchor. One per marathon; solving never touches it and RUN never freezes it. (#12, #13)
_Avoid_: plan (as a term of art), schedule

**Anchor**:
The one wall-clock datetime the whole timetable is positioned against, set by the admin in PICK; every box is an offset from it, so moving it moves the evening. This is where time enters the model: there is no day, session or multi-day concept. (#11, #12)
_Avoid_: start time, kickoff, day

**Box**:
A labelled span on the timetable: a film, fixed at its runtime, or something the admin draws such as a meal. The minutes between boxes are unoccupied, not a thing. (#12)
_Avoid_: block, slot, item, gap (as an entity)

**Overlap**:
Two boxes occupying the same minutes. Allowed and flagged, never prevented; the condition a ripple mode responds to. (#12, #13)
_Avoid_: clash, conflict, collision

**Use this slate**:
The one explicit action that lays a proposal's films onto the timetable back to back from the anchor, replacing what was there. The only path from proposals to the timetable. (#12, #17)
_Avoid_: push (a ripple mode), apply, import, sync

**Ripple mode**:
The timetable editor's sticky setting for what an edit does to the boxes it comes to overlap: leave them (the default), push them keeping gaps, or push them keeping the end time. Always chosen, never ambient; the same setting in PICK and RUN. (#12, #13)
_Avoid_: ripple (bare), cascade, reflow, auto-adjust

**Push**:
The movement a ripple mode applies to every box on one side of an edit, by the edit's own delta from the point of contact. Not undone by dragging back, since the reverse move touches nothing. (#13)
_Avoid_: shift, nudge

**Elapsed time**:
The span from the first box's start to the last box's end, gaps and meals included. Never compared against the budget. (#12)
_Avoid_: total time, duration, wall-clock length

**Presence strip**:
The contiguous span of the evening a voter is in the room for, derived from their vetoes and the current order alone. Not an attendance model; nobody is asked anything. (#11, #12)
_Avoid_: attendance, availability, window

**Shared time**:
The span of the evening every presence strip covers at once. The stacking cost a veto's flat price does not carry, made visible where the admin creates it. (#10, #12)
_Avoid_: overlap, common time

**Set readout**:
A number about a slate that changes when a film is added or removed and not when one is moved: floor, each voter's representative, Σrep, screen time against the budget, the size of the floor set, and which films are vetoed and by whom. Genre mix was one and was dropped; trigger warnings never appear here. (#12, #17, #20, #24)

**Arrangement readout**:
A number that changes when a box is moved: per-person presence strips and shared time. Derived from vetoes and order alone; nothing exogenous is ever entered. (#11, #12)

### Running

**RUN**:
The final phase, entered when the admin declares the plan settled, possibly days ahead; advancing to it publishes the timetable, which stays editable and is the voter's page, with the reveal behind it as a secondary view. Nothing follows it: the marathon ending is a fact about the world, not a state in the app. (#12, #13, #15, #27)
_Avoid_: marathon day, done, finished

**Actualising**:
Keeping the timetable true to the evening as it really runs, by editing it. The app holds no separate account of what actually happened. (#13)
_Avoid_: recording, tracking, actuals, planned-vs-actual

**Now playing**:
The box the present moment falls inside, derived on each reader's device from the anchor and offsets. Never stored and never marked by hand. (#13)
_Avoid_: current film, started/finished marks

### Trigger warnings

**Topic**:
One named thing that may happen in a film, carrying a crowd's yes and no counts as evidence rather than a verdict. (#5, #19, #20)
_Avoid_: trigger, tag, content descriptor

**Watched list**:
The topics a voter has declared they want to be told about. Private to that voter; never rendered to anyone else, the admin included. (#20)
_Avoid_: trigger profile, watchlist, trigger list (the page carrying the full vocabulary)

**Matched topic**:
A topic on a film that is also on the viewing voter's watched list, evaluated at the moment of viewing. Shown beside the veto control in VOTE; it never touches the objective and never vetoes on anyone's behalf. (#20)
_Avoid_: trigger warning (unqualified), hit, flagged topic

**Trigger icon**:
A film-level mark that at least one matched topic is well enough evidenced to assert. A claim about confidence, where the topic's own row is a claim about evidence. (#20)
_Avoid_: flag, badge, alert

**Uncovered**:
Of a candidate: having no crowd evidence bound to it at all, so an absence of warnings on it says nothing about its content. Distinct from a film whose evidence is merely thin. (#19, #20)
_Avoid_: no data, blank, unmatched (which describes a topic)

