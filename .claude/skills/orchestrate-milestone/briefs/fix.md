You are fixing review findings on ticket #{n}, "{title}", a sub-issue of milestone M{m} (#{parent}), in the Ribcage repo (C:\Ribcage_main, a Django app; Windows, Git Bash available). Read the ticket with `gh issue view {n} --comments` when a finding needs its context. A re-reviewer checks the fix.

## Findings

{every finding from the review, verbatim}

## Do
- **Fix every finding.** A behaviour fix comes with a test that fails before it.
- **Keep `CLAUDE.md` and the live docs true**, editing `CLAUDE.md` with the `writing-for-agents` skill.
- **Run the full default suite** with `.venv/Scripts/python -m pytest`. Done when it passes.
- **Browse** the state a page finding names, following `docs/agents/browser-verification.md`.
- **Commit once,** with `git commit --fixup={ticket_sha}` and the trailer `{trailer}`. Leave the history as it is, and push nothing.
- **Open questions:** where a fix leaves a choice open, make the one most consistent with the ticket and list it as a question.
- **GitHub and `private/` stay untouched.**

## Report (concise)
- the fixup SHA;
- per finding, what changed and the test that covers it;
- the suite counts;
- the questions for the dev.
