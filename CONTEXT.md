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
Which of six stages the marathon is in: SETUP, SUGGEST, APPROVE, VOTE, PICK, RUN. It decides which of the two user-writable surfaces, SUGGEST and VOTE, is live; it never gates the admin and moves freely in both directions. (#15)
_Avoid_: stage, step, status, state

### People

**Voter**:
A person registered into the marathon. The roster holds voters and nothing else, so "everyone" always means the whole roster. (#8)
_Avoid_: user, account, member, participant

**Admin**:
The person who runs the marathon and moves its phase, signing in with a credential that lives outside the roster. Never a voter and never counted as one. (#8)
_Avoid_: owner, host, organiser, moderator

**Join code**:
The one shared secret that admits a person to registration. Used exactly once per person; a gate, never a login credential. (#8)
_Avoid_: invite code, invite link, access code

**Display name**:
The unique name a voter chooses at registration and is known by everywhere. The only personal detail the app holds. (#8)
_Avoid_: username, handle, real name

**Roster**:
The list of everyone registered for the marathon. The control over who is in: looked at and pruned by the admin, never approved into. (#8)
_Avoid_: user list, membership, directory

**Attribution**:
The binding of every suggestion, score and veto to the voter who made it. A property of the model rather than of any screen, so "anonymous" can only ever mean hidden from other voters. (#8, #10)
_Avoid_: anonymity (as a claim about the app), authorship

**Reveal**:
The moment VOTE closes and every voter's scores become visible, per person, to the whole group. One-way; reopening VOTE does not undo it. (#8, #15)
_Avoid_: publish (that is what advancing to RUN does to the timetable), results

### Suggesting

**Suggestion**:
A film a voter puts forward in SUGGEST, attributed to them, waiting in the pool for the admin to approve or drop. (#8, #15)
_Avoid_: nomination, entry, submission

**Pool**:
The suggestions awaiting the admin's decision. Suggestions land here at any time, including after VOTE has opened. (#15)
_Avoid_: queue, backlog, candidate pool

**Picker**:
The step in SUGGEST where the suggester says which film they meant. Identity is always chosen by a person, never taken from search ranking. (#5, #19)
_Avoid_: autocomplete, search results, disambiguator

**Runtime**:
The length of the particular copy of a film the group will watch, not a fact about the film. Filled in from metadata and always editable by hand. (#5, #12, #15, #19)
_Avoid_: length, duration, official runtime

**Personal note**:
The suggester's own words attached to a suggestion. With scores hidden during VOTE, the only channel for persuading the group. (#8)
_Avoid_: comment, blurb, description

### Voting

**Candidate**:
A film the admin has approved out of the pool. The candidates are what VOTE and SOLVE work on; a film without a runtime cannot become one. (#5, #15)
_Avoid_: movie; not interchangeable with suggestion, the pre-approval state

**Ballot**:
The candidates put before voters in VOTE. Growing it while VOTE is open clears every voter's done marker, whoever added the film. (#15)
_Avoid_: candidate set, voting list

**Score**:
A voter's stated appetite for a candidate on a coarse five-point scale from "rather not" to "top pick", taken at face value and never normalised against anyone else's. Hidden from other voters until the reveal. (#8, #10)
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
A voter's own signal that they have finished with the current ballot, shown by name to the whole group. Reversible and never a lock on their votes; cleared for everyone when the ballot grows. (#15)
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
The voters the floor is computed over: everyone with at least one score, never everyone registered, minus anyone removed by the without-a-voter knob. (#8, #15, #17)

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
A group of proposals equal on floor and Σrep. Shown as tied, never ranked within. (#17)

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
A number about a slate that changes when a film is added or removed and not when one is moved: floor, each voter's representative, Σrep, screen time against the budget, genre mix, the size of the floor set, and which films are vetoed and by whom. Trigger warnings never appear here. (#12, #17, #20)

**Arrangement readout**:
A number that changes when a box is moved: per-person presence strips and shared time. Derived from vetoes and order alone; nothing exogenous is ever entered. (#11, #12)

### Running

**RUN**:
The final phase, entered when the admin declares the plan settled, possibly days ahead; advancing to it publishes the timetable, which stays editable. Nothing follows it: the marathon ending is a fact about the world, not a state in the app. (#12, #13, #15)
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

**Freeform note**:
The group's own free-text account of a film's content, editable by anyone in the group, covering whatever the crowd evidence does not. (#20)
_Avoid_: manual entry, disclaimer, content warning
