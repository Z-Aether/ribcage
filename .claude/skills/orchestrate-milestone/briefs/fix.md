You are fixing review findings on ticket #{n}, "{title}", a sub-issue of milestone M{m} (#{parent}), in the Ribcage repo (C:\Ribcage_main, a Django app; Windows, Git Bash available). Read the ticket with `gh issue view {n} --comments` when a finding needs its context. A re-reviewer checks the fix.

## Findings

{every finding from the review, verbatim}

## Do
- **Fix every finding.** A behaviour fix comes with a test that fails before it.
- **Keep `CLAUDE.md` and the live docs true**, editing `CLAUDE.md` with the `writing-for-agents` skill.
- **Run targeted tests:** the test files of each finding and of what you change. The orchestrator runs the full suite after the re-review. Done when they pass.
- **Browse** the state a page finding names, following `docs/agents/browser-verification.md`.
- **Commit once,** with `git commit --fixup={ticket_sha}` and the trailer `{trailer}`. Leave the history as it is, and push nothing.
- **Design questions:** where a fix leaves open what the app does or what a voter or the admin can do (a rule, a limit, a flow, what is kept or lost), make the choice most consistent with the ticket and list it as a design question. Wording, looks, layout, code placement and dev tooling are yours to choose: record each choice in `tmp/m{m}/{n}-comment.md`. The dev meets them while testing.
- **GitHub and `private/` stay untouched.**

## Report (concise)
- the fixup SHA;
- per finding, what changed and the test that covers it;
- the suite counts;
- the design questions.
