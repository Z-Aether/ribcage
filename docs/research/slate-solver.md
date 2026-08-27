# Slate solver: does this need integer programming, and what tooling exists?

Research for issue #6. Downstream consumers: #14 (tech stack), #17 (slate proposals), #12 (timetable).

**Package facts and licences checked 2026-08-27** against each project's own npm/PyPI metadata, repo and
docs. **Performance figures are measured, not quoted** — every number in §2, §5 and §6 comes from running the
actual model from #10 on this machine (Node v24.16.0, Windows 10, `highs@1.15.2`). The scripts are in
`docs/research/slate-solver/` and are reproducible: `npm install && node validate.js`.

Solve times fluctuate 2–3× run to run (WASM warm-up, JIT, GC). Ranges below are representative of several
runs, not single-shot bests. The orders of magnitude are what carry the argument, and those are stable.

---

## 1. Verdict

**Yes, model it as a MILP — and no, that is not the solver earning its place. The budget is.**

Two findings, and they point the same way:

1. **Exhaustive enumeration is correct and fast for a short marathon, and falls off a cliff for a long one.**
   Plain-JS enumeration of every budget-feasible slate over 50 films solves a 12-hour marathon in ~2.4 s and
   does not finish a 16-hour one in 60 s (§2). The cliff is driven by the **time budget**, which is a number
   the admin types into a box in PICK — not by anything the app controls.
2. **The MILP does not have a cliff at any size this app will ever see.** The same instances solve in
   **25–600 ms**, and the model still solves in ~3.7 s at **ten times** the stated ceiling — 500 films (§6).

So the honest framing is not "is the problem hard enough to deserve a solver". It isn't hard. The framing is
**which formulation's cost is independent of user input**, and only the MILP is. Enumeration would work right
up until the night someone decides on an all-nighter, and then it would hang.

**The learning goal is served, and it is not the reason.** The dev's stated interest in integer optimisation
would not have justified a solver on its own; here it comes for free with the choice that was correct anyway.

**Recommendation: `highs` (highs-js) — HiGHS compiled to WASM, MIT, one npm package that runs unchanged in
Node and in the browser.** Pin `>= 1.15.1` and set `mip_rel_gap: 0` (§7 — both matter, and the second one
bites silently).

**The browser-vs-server question does not have to be answered now.** Because the same package runs in both,
where the solve executes is a deployment detail that can be flipped later without touching the model. That
matters for #14: this research does *not* constrain the stack the way the hosting research did.

**One correction to a standing assumption.** The hosting research (#7) left standing advice to *"run the
solve as a job + poll"*. At 25–600 ms that is unnecessary — the solve fits comfortably inside a normal HTTP
request. The advice survives in exactly one place: Cloudflare Workers' 10 ms free CPU limit, which no
formulation here clears, so on Workers the solve must go to the browser regardless (§5).

---

## 2. The problem size, measured

### The model

Restating #10 in solver terms. `x[f]` = film in slate; `y[i,f]` = film `f` represents voter `i`.

```
max   K·W·m + K·Σ_i Σ_f s[i,f]·y[i,f] + Σ_f c[f]·x[f]
s.t.  Σ_f y[i,f] ≤ 1                for each voter i
      y[i,f] ≤ x[f]                 for each eligible pair
      m ≤ Σ_f s[i,f]·y[i,f]         for each voter i        (the protected floor)
      Σ_f r[f]·x[f] ≤ B             (the time budget — the only hard constraint)
      x, y binary;  0 ≤ m ≤ 3
```

`c[f] = Σ_i s[i,f]` is the total term `T` collapsed to one coefficient per film. `y[i,f]` exists only for
**eligible** pairs — not seen, not vetoed — which is what keeps the column count near 500 rather than 550.

Two properties of #10's model turn out to matter a lot and are worth naming:

- **`rep[i]` is bounded to `{0,1,2,3}`.** Because `Σ y ≤ 1` and representation floors at 0, a voter's
  representation can only take four values. This is why the maximin term is cheap: the floor variable `m` has
  a domain of size 4, not a continuous range.
- **The total term is separable.** `T` depends only on which films are chosen, never on who represents whom,
  so it collapses into the `x` coefficients and adds nothing to the model's difficulty.

At the stated ceiling (50 films, 10 voters) this is **~495 binaries and ~466 rows**. That is a *small* MILP
by any modern standard, which is exactly why the answer is so lopsided.

### Enumeration: correct, and cliff-edged

`enumerate.js` walks every budget-feasible subset in a DFS, films sorted by runtime ascending, pruning a
subtree the moment nothing further fits. It maintains `rep[]` incrementally and evaluates the exact #10
objective at every leaf — this is not an approximation, it is the true optimum by construction.

50 films, 10 voters, seed 7:

| Budget | Max slate size | Feasible slates | DFS nodes | Time | Finished? |
|---|---|---|---|---|---|
| 360 min (6h) | 4 | 11,663 | 23,325 | 9 ms | yes |
| 480 min (8h) | 5 | 141,481 | 282,961 | 54 ms | yes |
| 600 min (10h) | 6 | 1,382,034 | 2,764,067 | 326 ms | yes |
| 720 min (12h) | 7 | 11,098,746 | 22,197,491 | 2,441 ms | yes |
| 840 min (14h) | 9 | 74,305,780 | 148,611,559 | 17,717 ms | yes |
| 960 min (16h) | 10 | >285,000,000 | >570,000,000 | — | **no, aborted at 60 s** |
| 1080 min (18h) | 11 | >285,000,000 | >570,000,000 | — | **no, aborted at 60 s** |
| 1440 min (24h) | 14 | >296,000,000 | >592,000,000 | — | **no, aborted at 60 s** |

Roughly an **8× cost per extra two hours of budget**, and the counts for the aborted rows are lower bounds —
the true figures are far higher. A 24-hour marathon over 50 candidates is not a pathological input; it is a
plausible Saturday.

Note what *doesn't* drive this: the film count barely matters compared to the budget, because the budget is
what sets the slate size, and the slate size is the exponent.

### What about a DP?

Considered and rejected. The obvious dynamic program over `(film index, runtime used, rep vector)` has a
state space of `4^10` rep vectors × `B` runtime values ≈ **1M × 721 ≈ 7×10⁸ states before transitions**,
which is worse than the enumeration it was meant to replace, and it is only that small because `rep` happens
to be 2 bits wide. It also stops working the moment the scale in #10 is widened.

There is a good branch-and-bound to be written here — a decent upper bound would prune the 24-hour case
heavily. But writing it is *writing a solver*, which is the thing that would actually be wasted effort.

---

## 3. Solvers callable from JavaScript / TypeScript

| Package | Real MIP? | Latest release | Licence | Runtime | Verdict |
|---|---|---|---|---|---|
| **`highs`** (repo `lovasoa/highs-js`) | Yes — HiGHS branch-and-cut | 1.15.2, 2026-07-22 | MIT | WASM, Node **and** browser | **Recommended.** Proven solver core, permissive, one package for both runtimes. |
| `highs-addon` / `highs-solver` | Yes — same HiGHS core | 0.10.3, repo active Dec 2025 | Apache-2.0 | **Native addon, Node only** | Skip. No browser path, native-binary risk, behind on solver version. |
| `glpk.js` | Yes — real GLPK | 5.0.0, 2025-12-23 | **GPL-3.0** | WASM, Node + browser | Sound fallback; the copyleft is the only real objection. |
| `javascript-lp-solver` | Homegrown branch-and-cut | 1.0.3, 2026-01-24 | Unlicense | Pure JS | **Avoid.** Self-acknowledged correctness bug in its cutting-plane code, patched by deleting the broken part. |
| `yalps` | Homegrown, jsLPSolver lineage | 0.6.4, 2025-12-24 | MIT | Pure JS | **Avoid at this size.** Its own README recommends GLPK/HiGHS beyond "hundreds of variables" — this model is ~495. |
| `or-tools-wasm` (third-party) | Yes — CP-SAT, SCIP, CBC, GLPK | 0.9.1, repo pushed 2026-08-23 | Apache-2.0 | WASM, needs COOP/COEP headers in browser | Most capable, highest operational cost. Single-maintainer fork; **not** an official Google package. |
| `clp-wasm` | **No — LP only** | repo stale since 2021 | unclear | WASM | Red herring. CLP has no integer support at all. |
| lp_solve / standalone CBC WASM | — | no maintained build found | — | — | Do not exist in usable form. |

Notes that mattered when weighing these:

- **`javascript-lp-solver` and `yalps` share a lineage of hand-written branch-and-bound.** For a model whose
  whole value proposition is *"the answer is provably the best slate"*, a solver that has historically been
  wrong in its cut generation is disqualifying, and cheapness of API does not buy it back.
- **`or-tools-wasm` would give CP-SAT's `AddMinEquality`**, which expresses the maximin term natively instead
  of via the auxiliary-variable trick. That is genuinely more ergonomic — and it is also the single most
  instructive thing in this model to have to write by hand. For a project whose stated goal is *learning*
  integer optimisation, the trick being visible is a feature. See §8.
- There is **no official Google OR-Tools JS/WASM binding.** Verified, not assumed.

---

## 4. Solvers callable from Python

| Package | Licence (wrapper / solver) | Latest release | Install weight | Solver | Verdict |
|---|---|---|---|---|---|
| **OR-Tools CP-SAT** | Apache-2.0 | 9.15, 2026-01-14 | 22–30 MB wheel | CP-SAT | Best Python option. Native `AddMinEquality`; real solution pool. |
| **`highspy`** | MIT / MIT | 1.15.1, 2026-07-02 | **2.7–6.6 MB** | HiGHS | Leanest by far. Same engine as the JS recommendation. |
| `scipy.optimize.milp` | BSD-3 / MIT | ships with SciPy | ~0 marginal if SciPy present | HiGHS | Simplest one-shot call, but **no callback and no multi-solution support at all** — fails #17. |
| PuLP | MIT / CBC EPL-2.0 | 3.3.2, 2026-05-25 | ~16 MB + separate CBC | CBC (pluggable) | Fine, but CBC is now a separate install (`pulp[cbc]`) and is the weakest engine here. |
| `python-mip` | EPL-2.0 | 1.17.1, **2024-03-02** | bundles CBC | CBC | **Do not use.** Dormant since 2023–24, unresolved Python-version compatibility issues. |

For a pure-binary model, Google's own docs point at CP-SAT rather than their MPSolver wrapper: *"For integer
linear problems (ILP)… we recommend using the CP-SAT solver."*

**CP-SAT and the ε term.** CP-SAT works over integers, so `W·m + Σrep + ε·T` cannot use a fractional ε. This
is a non-issue — the fix is the same one this research used anyway: integerise, choosing `K` larger than
twice `max|T|` and writing the objective as `K·(W·m + Σrep) + T` (§7). `rep` and `T` are already integers, so
nothing needs scaling beyond picking `K`.

**Python is not recommended here**, but the reason is not the solvers — `highspy` and CP-SAT are both
excellent. It is that Python would add a second language to a project whose map explicitly asks to *minimise
language surface area*, and it would buy nothing the JS path doesn't already have, since both roads lead to
the same HiGHS engine.

---

## 5. Where the solve runs

Measured cold-start cost of `highs` (highs-js):

| | |
|---|---|
| Artifact | `highs.wasm` 3.43 MB + `highs.js` glue 70 KB |
| WASM instantiate | ~47 ms |
| First (warm-up) solve | ~115 ms |
| Steady-state solve, 50 films / 10 voters | **25–600 ms** |
| Node RSS after load | ~47 MB |

Three options, and the first two are the *same code*:

**(a) In the browser.** 3.4 MB is a real payload, but it is lazily loadable on the SOLVE screen only, and it
is downloaded by **one admin, a handful of times a year** — not by every voter on every page. 47 MB of WASM
heap is unremarkable for a desktop browser, and desktop is the priority per the map. This removes the
server-side solver runtime entirely, keeps Cloudflare Workers viable, and needs no background job.

**(b) On a Node server.** Identical package, identical model text. 47 MB RSS fits a 512 MB container with
room to spare. Solve inside the request handler.

**(c) On a Python server.** `highspy` (5 MB) or CP-SAT (30 MB). Works fine; costs a language.

**Runtime shape: a normal HTTP request, not a background job.** At 25–600 ms the solve is comparable to a
slow database query. Even the k-best loop of §6 — five diverse slates — lands at 0.5–2.2 s total, which is a
spinner, not a job queue. The only environment that forces otherwise is **Cloudflare Workers' 10 ms free CPU
limit** (flagged in #7), which nothing here clears; on Workers the solve must run client-side.

Because (a) and (b) are one package, **#14 does not need to decide between them to choose a stack.** It only
needs to not pick a host that forecloses (b) *and* a rendering model that forecloses (a).

---

## 6. k-best and diverse slates (for #17)

#17 asks whether enumerating several near-optimal, meaningfully-different slates is cheap. **It is, and the
answer contains a surprise that matters more than the timing.**

No open-source solver has a Gurobi-style k-best solution pool worth relying on. HiGHS has none (its
`mip_pool_*` options govern the internal *cut* pool, not solutions). CBC's pool is opportunistic — it retains
whatever incumbents branch-and-bound happened to pass through, with no diversity or count guarantee. CP-SAT
has a genuine `solution_pool_size`, but its `enumerate_all_solutions` mode is documented as not working *"if
the model contains an objective"*.

The portable answer is the **iterative diversity cut**: solve, then forbid solutions too close to the ones
already found, and re-solve. Forcing the next slate to differ from a previous slate `S` in at least `k` films
is one linear row:

```
Σ_{f ∉ S} x[f] − Σ_{f ∈ S} x[f]  ≥  k − |S|
```

At `k = 1` this is the classic no-good cut, which excludes exactly one point. Higher `k` is what actually
produces *different slates* rather than the same slate with one filler swapped — which is precisely the
distinction #17 raises.

Measured, 50 films / 10 voters / 720 min budget / seed 7, five successive proposals:

| Min. set-difference | 5 proposals in | Objective loss across all five |
|---|---|---|
| 1 film | 1,738 ms | 0 → 2 |
| **2 films** | **457 ms** | 0 → 2 |
| 3 films | 2,157 ms | 0 → 6 |

**The finding for #17 is not the speed, it is the flatness.** Every one of those losses is smaller than
`K = 4001`, meaning all five slates are **identical on the floor `m` and on `Σ rep`** and differ only in the
ε tie-break. All five had `m = 3` and all ten voters fully represented. The near-optimal region is not a
ranked list with a clear winner and a set of compromises — at this scale it is a **plateau of genuinely tied
slates**.

That reframes #17's question. Showing the admin three slates is not "here is the best one and two worse
ones"; it is "the maths cannot separate these, so pick with your eyes" — which is exactly the job #10 already
assigned to PICK, and it makes the case for diversity across proposals much stronger than a quality-ranking
view would.

The non-monotone timings are also worth noting: `k = 2` is *four times faster* than `k = 1`, because a
stronger cut prunes more than it constrains. Do not assume more diversity costs more.

---

## 7. Traps, in order of how quietly they bite

### 7.1 The default MIP gap silently defeats the ε tie-break — set `mip_rel_gap: 0`

**This is the one that will cost an afternoon if it isn't known up front.**

Cross-checking the MILP against exhaustive enumeration over 20 instances, one disagreed: seed 7 at a 720 min
budget, enumeration found **240133**, HiGHS returned **240132** — and reported status `Optimal`.

The cause is not a bug. HiGHS's default relative MIP gap is `1e-4`; at an objective of ~240,000 that tolerates
**24 units of absolute slack**, while the entire ε tie-break term spans less than `K = 4001` and the
individual differences being tied-broken are worth 1. The solver was working exactly as documented, and the
tie-break was inside its noise floor.

```
options {}                                  status=Optimal obj=240132   (413 ms)
options {"mip_rel_gap":0}                   status=Optimal obj=240133   (264 ms)
options {"mip_rel_gap":0,"mip_abs_gap":0}   status=Optimal obj=240133   ( 58 ms)
```

With `mip_rel_gap: 0, mip_abs_gap: 0`, **all 20 cross-checks agree exactly** (`validate.js`). Closing the gap
also happened to be *faster* here, so there is no cost to pay.

The general lesson generalises past HiGHS: **any objective built from a large primary term plus a small
tie-break term is at risk from relative gap tolerances**, on every solver. If the model ever moves to CP-SAT
or CBC, the equivalent tolerance must be zeroed there too.

### 7.2 Pin `highs >= 1.15.1`

HiGHS 1.14.0 shipped a presolve regression that returned a **suboptimal solution labelled `Optimal`** on
trivial MIPs (`lovasoa/highs-js` issue #53 — reporter saw 15 against a true optimum of 9), traced to
`HPresolve::singletonColStuffing` not recomputing row activity for integer columns. Fixed in 1.15.0/1.15.1.
The currently published 1.15.2 is clear. This is the same failure class as 7.1 arriving from a different
direction, and it is the reason the cross-check in `validate.js` is worth keeping around rather than
deleting once it passes.

### 7.3 The objective comes back as a float

Observed: `196114.000000003`. Round before comparing or storing. Do not compare objectives with `===`.

### 7.4 Integerise the objective rather than using a fractional ε

Write `K·(W·m + Σ rep) + T` with `K > 2·max|T|`. At the stated ceiling `max|T| = 3·10·50 = 1500`, so
`K = 4001` is safe. This keeps every coefficient an integer, removes a class of floating-point tie-break
bugs, makes the objective readable (`obj ÷ K` is the primary value, `obj mod K` the tie-break), and is
required outright if the model ever moves to CP-SAT.

---

## 8. What this implies downstream

**#14 (tech stack)** — This research **does not constrain the stack**, which is the useful part. TypeScript
front-to-back with `highs` is the lowest-language-surface path and keeps both deployment shapes open. Python
is viable but costs a second language for no engine advantage — `highspy` and `scipy.optimize.milp` are the
same HiGHS. Anything that can run a Node process or serve a WASM file is sufficient. The one live constraint
is unchanged from #7: **Cloudflare Workers forces the solve into the browser.**

**#14, on the learning goal** — the LP-format path teaches more than CP-SAT's. `AddMinEquality` hides the
maximin linearisation; writing `m ≤ Σ s[i,f]·y[i,f]` by hand is the single most instructive line in the
model, and the `y[i,f] ≤ x[f]` linking constraint is the second. If integer optimisation is the thing being
learned, prefer the formulation that makes you write them.

**#17 (slate proposals)** — unblocked, with a stronger answer than "it's cheap": the top slates are *tied*,
not ranked (§6). A minimum set-difference of 2 films is measurably the sweet spot. Budget ~0.5 s for five
proposals.

**#12 (timetable)** — unaffected. Vetoed films still need edge-block placement, and SOLVE still imposes no
veto-derived feasibility constraint, exactly as #10 specified. Nothing in the tooling changes that.

**#7 / #18 (hosting)** — the *"run the solve as a job + poll"* standing advice can be dropped everywhere
except Cloudflare Workers. This removes a background-worker requirement from the hosting shortlist, which
simplifies the Render/Fly/Supabase comparison rather than changing its ranking.

**Fog: "whether solve results are stored, re-runnable, or recomputed live"** — the performance half of that
question is now closed. At ~50 ms, recomputing on every page load is free, so persistence is purely a
UX/auditability question ("is the slate the admin picked the same object everyone saw?"), not a performance
one. Left in the fog because the remaining half is entangled with #15 and #17.

---

## 9. Reproducing

```
cd docs/research/slate-solver
npm install
node enumerate.js   # the enumeration cliff (§2)  — ~3 min, three rows time out by design
node mip.js         # MILP solve times (§1, §5)
node validate.js    # MILP vs exhaustive, 20 instances (§7.1)
node gap.js         # the mip_rel_gap trap, isolated (§7.1)
node kbest.js       # diverse k-best loop (§6)
node scale.js       # headroom past the stated ceiling (§6)
```

`instance.js` generates deterministic instances: runtimes drawn from a realistic distribution (median 116
min, a tail of 150–210 min epics), hand scores −1…+3 skewed to the middle, 2% veto rate, 10% seen rate.
Change the seed to test others — `validate.js` covers five.

**Headroom** (`scale.js`), for reference on how much room the recommendation has:

| Films | Voters | Budget | Binaries | Rows | Solve |
|---|---|---|---|---|---|
| 50 | 10 | 720 | 495 | 466 | 360 ms |
| 50 | 10 | 1440 | 495 | 466 | 361 ms |
| 100 | 10 | 1440 | 977 | 898 | 120 ms |
| 200 | 10 | 1440 | 1,948 | 1,769 | 2,336 ms |
| 500 | 10 | 1440 | 4,911 | 4,432 | 3,662 ms |
| 200 | 50 | 2880 | 9,034 | 8,935 | 596 ms |

Ten times the films and five times the voters is still a few seconds. The stated ceiling is not close to any
edge.

---

## 10. Sources

All verified 2026-08-27.

- [highs-js repo](https://github.com/lovasoa/highs-js) · [`highs` on npm](https://www.npmjs.com/package/highs) · [issue #53, the 1.14.0 presolve regression](https://github.com/lovasoa/highs-js/issues/53)
- [HiGHS option definitions](https://ergo-code.github.io/HiGHS/dev/options/definitions/) (`mip_rel_gap`, `mip_pool_*`) · [HiGHS further features / warm starts](https://ergo-code.github.io/HiGHS/dev/guide/further/) · [HiGHS callbacks](https://ergo-code.github.io/HiGHS/dev/callbacks/)
- [glpk.js repo](https://github.com/jvail/glpk.js) · [javascript-lp-solver issue #64, MIR cuts bug](https://github.com/JWally/jsLPSolver/issues/64) · [YALPS repo](https://github.com/Ivordir/YALPS) · [or-tools-wasm repo](https://github.com/Axelwickm/or-tools-wasm) · [clp-wasm repo](https://github.com/centrifuge/clp-wasm)
- [OR-Tools CP-SAT solver docs, `enumerate_all_solutions` restriction](https://github.com/google/or-tools/blob/stable/ortools/sat/docs/solver.md) · [`sat_parameters.proto`, `solution_pool_size`](https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto) · [CP-SAT integers-only guidance](https://developers.google.com/optimization/cp/cp_solver) · [MIP solver recommendation](https://developers.google.com/optimization/mip/mip_example) · [`ortools` on PyPI](https://pypi.org/project/ortools/)
- [`highspy` on PyPI](https://pypi.org/project/highspy/) · [`scipy.optimize.milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) · [PuLP on PyPI](https://pypi.org/project/PuLP/) · [PuLP install docs, CBC no longer bundled](https://coin-or.github.io/pulp/main/installing_pulp_at_home.html) · [python-mip releases](https://github.com/coin-or/python-mip/releases)
- No-good / Hamming-distance cuts: [GAMS integer-cut example](https://www.gams.com/latest/gamslib_ml/libhtml/gamslib_icut.html) · [Pyomo `alternative_solutions`, Hamming search mode](https://pyomo.readthedocs.io/en/stable/explanation/analysis/alternative_solutions.html)
- One-shot diverse formulations, considered and rejected as impractical here: [DiversiTree (arXiv:2204.03822)](https://arxiv.org/abs/2204.03822) · [Danna et al., *Generating Multiple Solutions for MIP*](https://link.springer.com/chapter/10.1007/978-3-540-72792-7_22) (metadata only; full text paywalled)
