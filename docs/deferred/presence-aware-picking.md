# Presence-aware PICK

> **STATUS: DEFERRED. NOT IN SCOPE. NOT A SPECIFICATION.**
>
> This document describes a design that was worked out in full and then
> **deliberately not adopted**. The decision of record is
> [#11 — Attendance: does the app model who is present when?](https://github.com/Z-Aether/ribcage/issues/11),
> which resolved that **attendance is not modelled at all**.
>
> Nothing here should be built. It is written down so that the next person
> who feels this itch does not have to redo the session that produced it.

Worked out 2026-08-29 while resolving #11.

## The itch

[#10 — Objective and vetoes](https://github.com/Z-Aether/ribcage/issues/10) charges every hard veto a
flat **−2**. That number is not the vetoer's opinion of the film — #10 is explicit that
_"the −2 prices absence, not viewing… it is the cost to the group of losing them for it."_
It is a **group-level charge for lost shared time**, which happens to be stored in the score matrix.

But sometimes no shared time is lost. If Alice was leaving at 1am regardless of what is playing,
then scheduling the film Alice vetoed at 1am costs the group **nothing** — she was already gone.
The flat −2 overcharges, and the solver is discouraged from a veto that is actually free.

This is not hypothetical. It is how the group already operates: **exogenous absence (the outside
world takes someone) is used as a resource to pay for endogenous absence (someone wants to skip a
film).** The design below mechanises that alignment.

## Two populations of absence

|                                                        | Source            | Covered by #10? |
| ------------------------------------------------------ | ----------------- | --------------- |
| **Endogenous** — "I'm stepping out for _that film_"     | a veto            | Yes, fully      |
| **Exogenous** — "I'm not there before 8 / after 1am"    | the outside world | No              |

The design exists only to price the interaction between them.

## Governing principle

> **Generation may be sloppy. Scoring must be honest.**

A sloppy _candidate_ claims nothing — it is one more slate on the table for a human to price.
A sloppy _score_ comes back labelled `Optimal` and is believed. Every placement decision below
follows from this split.

## The design

### Collection — admin-only, in PICK

Presence is entered **by the admin, during PICK, and never asked of a user.**

Two reasons, both load-bearing:

1. **The user-facing surface stays date- and time-agnostic.** Date-finding is out of scope for this
   app. The moment any user-facing screen asks about clock time, it has quietly become a scheduling
   poll. Under admin-only entry the entire time dimension lives on the admin's side of the wall.
2. **Staleness.** A window is the least stable input in the system. Scores, vetoes and seen-it are
   stable facts about a person's taste; _"I have to leave at 1"_ is a fact about one specific
   Saturday, and real life moves it. The admin holds the freshest version, in the group chat, on
   the day.

A third reason, weaker but real: a user-declared window that the app then optimises around converts
_"I'll probably head off around 1"_ into _"the night is built assuming you leave at 1."_ That is the
app taking a social position on someone's behalf. An admin-entered value is a person recording what
a person told them.

**Windows are contiguous — a prefix and/or a suffix of the night, never a hole in the middle.**
This matches #10's leading/trailing block model exactly and is what makes absence arrangeable.
Mid-night gaps ("ducking out for a call") are the one case the admin can genuinely hold in their
head, and allowing them costs the invariant that makes the rest coherent.

### Derivation — presence is computed, not entered

The admin enters a window. The **arrangement** decides which films fall inside it. Every
(person, film) pair in the slate is therefore in exactly one of **three** states:

| State                                 | Contributes to `T` | Meaning                                              |
| ------------------------------------- | ------------------ | ---------------------------------------------------- |
| **Present**                           | `s[i,f]`           | normal                                               |
| **Absent — covered by their window**  | **0**              | they were gone anyway; the group lost nothing        |
| **Absent — veto-induced**             | **−2**             | they _would_ have been in the room; the group lost them |

The middle row is the entire feature.

**The three states are not optional.** A naive binary "absent → 0" rule is wrong and silently
destructive: #10's hard constraint means a vetoed film is in the slate _only if_ the vetoer is
absent for it, so `present = false` holds **by construction** for every vetoed pair. A binary rule
therefore zeroes the −2 in every slate, reopening the exact hole #10's amendment was written to
close — _"a film four people love and one vetoes scores identically to one four people love and
nobody minds."_

**Partial overlap is charged.** If a vetoed film runs 00:30–02:30 and Alice leaves at 01:00, the
pair is **veto-induced (−2)**, not prorated. If she is in the room when a film she vetoed starts,
the arrangement is wrong and the number should say so. Proration would introduce exactly the kind
of fudge factor #10 rejected everywhere else.

### Scoring — planned vs. actual

PICK shows **two** numbers per slate, and they are different quantities by design:

```
planned:  #10's objective, vetoes at a flat -2   (what SOLVE computed)
actual:   recomputed under THIS arrangement and THIS presence data
```

```
rep_actual[i]  = best-scoring film in the slate that i is PRESENT for,
                 not seen, not vetoed          (0 if none)
m_actual       = min_i rep_actual[i]
T_actual       = sum over pairs, per the three-state table above
```

Drag a film; the numbers move. Put a vetoed film where the vetoer was already gone and −2 becomes 0.

**SOLVE cannot compute `actual`.** The veto's true price is arrangement-dependent, and SOLVE has no
arrangement. It keeps the flat −2. The UI must never present the two numbers as the same quantity.

### Generation — hypothesis re-solves

Since SOLVE runs in 25–600 ms ([#6](https://github.com/Z-Aether/ribcage/issues/6)) it is a
**subroutine callable from PICK**, not a phase before it. So PICK can re-solve with hypotheses:

- **Veto-freeing scenarios.** For each person with a declared window, one extra solve with **their**
  veto penalties zeroed (−2 → 0). This surfaces slates containing films _only that person_ objected
  to — precisely the ones the flat −2 was wrongly suppressing.
- **Each proposal carries its hypothesis as a label**: _"Best if Alice is out for Hereditary."_
  The admin can reject the premise outright.
- **Cost**: one solve per windowed person. Two windowed people ≈ 100 ms.

This is deliberately tighter than letting the solver pick _k_ films to ignore per user: the free
films are **derived from a declared absence** rather than guessed, and every proposal is explainable
in one sentence — the standard #10 held every mechanism to.

## What this design is actually for

**Not the matching.** Matching 1–2 windows against 1–3 vetoes is trivial by eye, and the group
already does it unaided. The app computing it is ceremony.

**The collateral damage of the matching.** Moving a vetoed film to an edge **displaces everything
else**. The film Bob rated +3 slides past the point where Bob leaves. Bob's floor is now 0 and
nobody notices — because the person who lost out is not the person the rearrangement was about, and
the admin was looking at Alice.

That is invisible by eye across 8 people, and it is exactly the failure #10's `min(rep)` floor
exists to prevent. A live **actual** floor catches it the instant the admin drags.

**#11 judged that second-order displacement rare enough to eat.** That judgement is the single
condition this whole design hangs on. It is most likely to be wrong when **a window is tight
relative to the budget** — an all-nighter with someone who leaves at 1am puts _hours_ of slate
outside their window, and the odds their representative lands there are not small.

## Why it is deferred, not built

The cost is an admin window-entry UI, presence derivation from the arrangement, three-state pair
accounting, a dual planned/actual readout, and hypothesis re-solve plumbing. Against a baseline of:
_the admin knows Alice leaves at 1, drags the vetoed film to the end, done._

For the first-order problem the baseline is genuinely sufficient. Only the second-order effect earns
the machinery, and #11 called it rare.

## Rejected on the way here

**Feeding windows to SOLVE's objective.** Cost was never the objection — the model adds ~10–30
binaries to #6's ~495, well inside measured headroom. The objection is that it **returns a
confidently wrong answer**:

> Alice arrives 2h late. Bob leaves 2h early. Both veto _X_ (2h).
> An aggregate free-absence-budget model says _X_ is free for both — each has 2h of budget, _X_
> costs 2h. Predicted veto cost: **0**.
> But _X_ goes in **one** block. Leading → Bob is there for it. Trailing → Alice is there for it.
> True cost: **−2**, always.

SOLVE would label that slate optimal and PICK would discover the promise cannot be kept — the same
failure mode #6 flagged for `mip_rel_gap`. The only non-lying version requires SOLVE to assign films
to blocks and order them, i.e. **SOLVE does the timetable**, which #10 explicitly ruled against
(_"that half is not the solver's problem"_).

**A post-VOTE window-collection phase.** Dominated. It needs its own screen, its own gate and its
own nag ("3 of 5 have submitted") — the exact cost
[#8](https://github.com/Z-Aether/ribcage/issues/8) used to reject the approval queue — to obtain
data the admin can enter in PICK, later and fresher.

**An optional window field on the VOTE ballot.** Cheaper than a phase (it rides a screen everyone
already visits), but it breaks the date/time-agnostic user surface for a value that will be stale
by PICK.

**Deriving attendance from vetoes.** Already the case — that is what #10 does. It is the endogenous
row of the table, and it needs no new concept.

**Mid-night presence gaps.** See above.

## What #11 kept

Two things from this design survived into the resolution of record, because they are useful without
any presence model at all:

- **PICK can re-invoke SOLVE with admin-chosen what-ifs** — exclude a voter from the floor term,
  or disregard a voter's vetoes. Solver knobs on the admin's side, no clock and no window.
  Handed to [#17](https://github.com/Z-Aether/ribcage/issues/17).
- **SOLVE is a subroutine of PICK, not a gated phase before it.**
  Handed to [#15](https://github.com/Z-Aether/ribcage/issues/15).
