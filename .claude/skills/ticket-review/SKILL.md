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
  - a test that passes without the code it covers;
  - a gap in a meta-test such as `tests/http/test_route_kinds.py` or `test_phase_check.py`;
  - a name that contradicts `GLOSSARY.md`;
  - an untrue line in `CLAUDE.md`, a live doc or a drafted ticket comment;
  - a layout that breaks or shifts at one width.

Every finding gets fixed, so the grade orders the work. A remark that can't cause a problem, such as a preference, a polish idea or a nicer name, is no finding: leave it out of the report entirely.

Behaviour a voter would find wrong, like a note shown twice, a field that jumps or typing that is lost, is a finding even where no doc covers it. A **question** is a choice between behaviours that both work, which the ticket and the live docs leave to the dev.

## Steps

1. **Pin the change.** You get a range, `<base>..HEAD`, and usually the implementer's report. Run `git log --oneline <range>` and `git diff --stat <range>`, and check that `git status` is clean. Read the ticket and its parent with `gh issue view <n> --comments`. The ticket carries the decisions it needs, each citing its source. Open a cited ticket or doc section only to settle a question the ticket leaves open.
2. **Read the diff whole.** Use `git diff <range>`, file by file for a long one.
3. **Prove each acceptance criterion.** For every criterion, name the test that covers it. Then make the test bite:
   - Break the code it covers by reverting a line or flipping a condition.
   - Run that test and see it fail.
   - Restore with `git checkout -- <file>`.

   Done when every criterion has a test that failed against broken code and `git status` is clean again. A criterion with no test, or a test that passed against broken code, is a finding.
4. **Check the rules** against the diff:
   - `CLAUDE.md` stays true for everything the change touched, in its Layout lines above all.
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
6. **Run the full default suite** with `.venv/Scripts/python -m pytest`. A failure is a finding.
7. **Report.** Write the report to the path your brief names, else return it:
   - **Verdict:** clean, or the number of findings.
   - **Findings**, highest grade first. Give each one its grade, `file:line`, the problem it causes and the direction of the fix.
   - **Criteria**, first review only: each acceptance criterion and the test that proves it.
   - **Questions for the dev**, each with the options you see.
   - **Suite counts.**

## Re-review

A re-review gets the fixup commits as its range and the findings they answer.

- For each finding, check that it is fixed. A behaviour fix needs a test that bites, proved as step 3 does.
- Check the fixups for new problems with steps 2 and 4.
- Browse, as in step 5, only the states a fixup touched.
- Run the full suite, then report as in step 7, leaving out the criteria list.
