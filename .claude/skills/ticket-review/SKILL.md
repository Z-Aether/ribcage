---
name: ticket-review
description: Review a Ribcage ticket's commits against the ticket and the repo's rules, reporting only findings that can cause a problem. Use when reviewing a ticket's implementation, re-reviewing fixups to it, or reviewing commits since a point.
---

# Ticket review

One agent reviews one ticket's commits: does the change do what the ticket asks, and does it keep the repo's rules? The repo is yours to read and to probe, and the tree ends as you found it: you write only under `tmp/`, and you commit, push and post nothing.

## Findings

A **finding** is something in the change that can cause a problem. Grade each one:

- **critical**: loses or leaks data, opens a wall (the login, the admin wall, the phase check), or breaks the deployment.
- **high**: an acceptance criterion unmet, or behaviour a voter or the admin would meet as a bug.
- **mid**: a problem that bites later:
  - an owed test that is missing, or that passes without the code it covers;
  - a pin: a test that asserts tags, class names, element counts or a file's source text, so it breaks on a restyle and never on a bug;
  - a gap in a meta-test such as `tests/http/test_route_kinds.py` or `test_phase_check.py`;
  - a name that contradicts `GLOSSARY.md`;
  - an untrue line in `CLAUDE.md`, a live doc or a drafted ticket comment;
  - a layout that breaks or shifts at one width.

Every finding gets fixed, so the grade orders the work. A remark that can't cause a problem, such as a preference, a polish idea or a nicer name, is no finding: leave it out of the report entirely.

Behaviour a voter would find wrong, like a note shown twice, a field that jumps or typing that is lost, is a finding even where no doc covers it. A **design question** is a choice the ticket and the live docs leave open about what the app does or what a voter or the admin can do: a rule, a limit, a flow, what is kept or lost. Wording, looks, layout, code placement and dev tooling are the implementer's to choose, and the dev meets them while testing.

## Steps

1. **Pin the change.** You get a range, `<base>..HEAD`, and usually the path of the implementer's report. Run `git log --oneline <range>` and `git diff --stat <range>`, and check that `git status` is clean. Read the ticket and its parent with `gh issue view <n> --json title,body,comments --jq '.title, .body, .comments[].body'`. The ticket carries the decisions it needs, each citing its source. Open a cited ticket or doc section only to settle a question the ticket leaves open.
2. **Read the diff whole.** Use `git diff <range>`, file by file for a long one.
3. **Prove each acceptance criterion.** `CLAUDE.md`'s `tests/` lines say which criteria owe a test.
   - **A criterion that owes a test:** name the test that covers it, then make it bite.
     - Break the code it covers by reverting a line or flipping a condition.
     - Run that test, or its file alone, and see it fail.
     - Restore with `git checkout -- <file>`.
   - **Every other criterion:** see it hold in the browser, in step 5. It needs no test, and a test written for it is held to the pin rule above.

   Done when every criterion that owes a test has one that failed against broken code, every other criterion has a browsed state, and `git status` is clean again.
4. **Check the rules** against the diff:
   - `CLAUDE.md` stays true for everything the change touched, and its Layout grows only as that section's own rule allows.
   - Commits are one short line ending in the ticket number.
   - Comments are one short line, citing a ticket where there is one.
   - Identifiers, CSS classes and copy use `GLOSSARY.md`'s terms. Grep it for each new name.
   - A decision made in the build is in `docs/design.md`, `docs/milestones.md` or `docs/theme.md`, citing the ticket, and in the drafted ticket comment.
   - A styled page follows `docs/theme.md`.
   - A new route carries the marks `tests/http/routes.py` reads, and a voter write carries `phase_window`.
   - Duplicated logic that will drift apart, or a name that misleads, is a finding.
5. **Browse it**, when the change touches a page:
   - Read the implementer's screenshots first. An image already taken can show the bug.
   - Then follow `docs/agents/browser-verification.md` over every state the change touches, at both widths.
   - Favour the states the implementer's run left out: refusals, empty states, the card after a swap, a second action after the first.
6. **Run the test files the diff touches** in one run. A failure is a finding. The full suite is left to whoever lands the change, unless your brief asks for it.
7. **Report.** Write the report to the path your brief names and return what the brief asks for; with no path, return the report itself. It holds:
   - **Verdict:** clean, or the number of findings.
   - **Findings**, highest grade first. Give each one its grade, `file:line`, the problem it causes and the direction of the fix.
   - **Criteria**, first review only: each acceptance criterion and its proof, the test or the browsed state.
   - **Design questions** the implementer's report doesn't already raise, each with the options you see.
   - **Suite counts.**

## Re-review

A re-review gets the fixup commits as its range and the findings they answer.

- For each finding, check that it is fixed. A fix that owes a test needs one that bites, proved as step 3 does; any other fix needs its state browsed.
- Check the fixups for new problems with steps 2 and 4.
- Browse, as in step 5, only the states a fixup touched.
- Run the test files the fixups touch, then report as in step 7, leaving out the criteria list.
