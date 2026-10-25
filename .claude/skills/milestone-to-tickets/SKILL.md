---
name: milestone-to-tickets
description: Break a Ribcage milestone into self-contained sub-issues under its parent, through to-tickets; or revise a milestone's open sub-issues into that shape.
disable-model-invocation: true
---

# Milestone to tickets

Break milestone M<n> into implementation tickets, each **self-contained**: an implementer who reads only the ticket, its parent and what the ticket's Context names can build it. The decisions are spread across the design record (map #4 and its tickets), the live docs and the parent's comments. You read them whole once, here, and each ticket carries a cited copy of every decision it needs. The implementer, the reviewer and every re-reviewer read the ticket, so a decision it leaves out is a record they each read whole again.

## Steps

1. **Load to-tickets.** Read `.claude/skills/to-tickets/SKILL.md` and follow its process with the changes below. Where the two differ, this skill wins. Also read the Milestone operations in `docs/agents/issue-tracker.md`.
2. **Revise the parent with the dev.** The parent's body is a baseline until the breakdown. Done when the dev approves its revised body.
3. **Gather the decisions.** This replaces to-tickets' steps 1 and 2. Read:
   - the parent with its comments;
   - `docs/milestones.md`'s section for M<n>;
   - the `docs/design.md` sections the milestone touches;
   - every ticket they cite, with its comments, where the last dated amendment wins;
   - the notes left for this milestone on its parent;
   - the code the milestone extends, starting from the apps `CLAUDE.md`'s Layout names.
4. **Draft and quiz** as to-tickets' steps 3 and 4 say.
5. **Write each ticket** from the template below. Done when:
   - every decision you gathered that bears on a ticket is in its "What to build", cited;
   - each acceptance criterion is concrete enough to name its test.
6. **Publish** as to-tickets' step 5 and the Milestone operations say: each ticket a sub-issue of the parent, with its triage label and native blocking edges.

## Revising open tickets

When the dev asks to bring a milestone's open sub-issues into this shape:

1. **Gather** as step 3 says, adding every comment on the open sub-issues and any notes the dev points you to.
2. **Rewrite** each open ticket's body from the template.
   - Keep its number, title and blocking edges, and every decision it holds.
   - Fold in the dated comments that amend it, citing them.
   - A change of scope or a new decision is the dev's to make: list it as a question.

   Closed tickets stay as they are.
3. **Show** the dev each new body. Publish on approval with `gh issue edit <n> --body-file <file>`.

## Ticket template

This replaces to-tickets' issue template. Use `GLOSSARY.md`'s terms throughout.

```markdown
## Parent

#<parent>

## What to build

The end-to-end behaviour from the voter's or admin's side, with every decision the
build needs stated whole and its source cited in brackets: a ticket (#26), a dated
amendment (#26, 2026-10-12), a live doc (design.md §8), a sibling's build note (#88).

## Context

- **Read:** the `docs/design.md` sections by number and heading; `docs/theme.md` when it builds or styles a page.
- **Builds on:** the modules, components and helpers it extends, by their module paths and names in the code.
- **Leaves room for:** what a later sibling needs from this one's markup or interface, naming the sibling.

## Acceptance criteria

- [ ] An observable outcome; a page criterion names the state to browse, such as "a refused runtime, at both widths".
```

**Builds on** names code, against to-tickets' advice on file paths. Tickets here are built within days of being written, so those names still hold when they are.
