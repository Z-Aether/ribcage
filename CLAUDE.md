# Ribcage

A web app a group of friends uses to plan and run one film marathon. It is rebuilt for each marathon and torn down afterwards. The repo is public.

**Keep this file true.** When you deliberately change the repo so that a line here no longer holds, update that line in the same commit, editing with the `writing-for-agents` skill.

## Finding things

- **Words** mean what `GLOSSARY.md` says they mean. Use its terms in code, tests and tickets, identifiers included.
- **What** gets built is in `docs/design.md`, and **in what order** is in `docs/milestones.md`. Both are condensed from the tickets.
- **Work to do** lives on milestone tickets: one parent per milestone, its implementation tickets as sub-issues wired with native blocking edges. They are kept apart from the map.
- **Why** something is the way it is: look up the ticket cited beside it (`#n`, read with `gh issue view <n> --comments`). The ticket is the decision of record, and its last dated amendment wins. Map #4 links every design ticket.
- **Prototypes and research write-ups** live on branches: `prototype/<screen>` and `research/<topic>`. The ticket that produced one names its branch. Read them with `git show <branch>:<path>`.

## Layout

Top-level directories sort by what a thing is, not by which ticket made it. A new kind of thing gets its directory and its line here.

- `docs/` is prose. `docs/deferred/` holds designs that were worked out and then shelved. `docs/agents/` configures skills and is reached through the pointers below.
- `fixtures/` is recorded data, grouped by subject, that tests and seeding read offline. It holds data only.
- `tools/` holds standalone harnesses from research tickets, one directory each. They stay outside the app and never ship.
- `private/` holds credentials and the group's real data. Its contents stay on this machine, out of commits, tickets and logs.
- `tmp/` is scratch, and nothing durable points into it.

**Ignored files are part of the layout.** `private/`, `tmp/` and some of `fixtures/` are gitignored, so `git ls-files` won't show them. Check `.gitignore` before concluding a file is missing.

## Commits

- **Commit freely; the dev alone pushes.** Everything after `@{u}` is still yours to rewrite: reorder, squash and fixup until each commit is one standalone feature or module, splitting a ticket across several commits where it holds several.
- **Messages are one short line.** An implementation commit ends with the ticket it resolves: `Add the phase check to VOTE (#34)`.
- **Code documents itself** through names. A comment is one short line telling a later agent about a non-obvious decision, citing its ticket where there is one.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues on `Z-Aether/ribcage`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its role name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repo root. Decisions are recorded on tickets rather than ADRs.
