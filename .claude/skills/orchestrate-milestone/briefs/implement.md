You are implementing ticket #{n}, "{title}", a sub-issue of milestone M{m} (#{parent}), in the Ribcage repo (C:\Ribcage_main, a Django app; Windows, Git Bash available). A reviewer checks your work afterwards.

## Read
- **The ticket and its parent:** `gh issue view {n} --comments` and `gh issue view {parent} --comments`. The ticket carries the decisions it needs, each citing its source, and the last dated amendment wins.
- **What its Context names:** the design sections, the modules it builds on, and `docs/theme.md` when it builds or styles a page.
- **What this batch built that you use:** {handoff lines for #n, earlier commits and what they hold, or "nothing"}
- **Everything else on demand.** Open a cited ticket, another doc section or a sibling ticket only to settle a question the ticket leaves open. Grep `GLOSSARY.md` for the terms you name things with.

## Do
- **Build** what the ticket's "What to build" asks, test-first where it fits (the `tdd` skill).
- **Test** every acceptance criterion, in the suite `CLAUDE.md`'s Layout gives it.
- **Keep `CLAUDE.md` true**, editing with the `writing-for-agents` skill.
- **Record decisions.** A decision that changes `docs/design.md`, `docs/milestones.md` or `docs/theme.md` updates their lines in the same commit, citing #{n}.
- **Run the full default suite** with `.venv/Scripts/python -m pytest`. Done when it passes.
- **Browse it** by following `docs/agents/browser-verification.md`, at both widths. Save screenshots as `tmp/m{m}/{n}-…png`.
  - States to check: {the states the acceptance criteria name}.
  - Stop the seeded server when you're done.
- **Commit** in one or more commits, each a standalone feature or module.
  - Each message is one short line ending in `(#{n})`, then a blank line and `{trailer}`.
  - Leave everything before `{base}` as it is, and push nothing.
{ticket-specific notes, or delete this line}

## Leave to the dev
- **GitHub stays untouched.** Draft any ticket comment the work warrants, such as a decision made during the build, in `tmp/m{m}/{n}-comment.md`.
- **Design questions:** where the ticket and the live docs leave open what the app does or what a voter or the admin can do (a rule, a limit, a flow, what is kept or lost), make the choice most consistent with them and list it as a design question. Wording, looks, layout, code placement and dev tooling are yours to choose: record each choice in the drafted ticket comment. The dev meets them while testing.
- **`private/`** stays untouched.

## Report (concise)
- the commit SHAs and messages;
- what you built, and where;
- each acceptance criterion and the test that covers it;
- the suite counts;
- the states you browsed and the screenshot paths;
- the design questions;
- anything left undone or uncertain.
