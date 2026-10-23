---
name: orchestrate-milestone
description: Oversee the build of a milestone's tickets from the main session, delegating each implementation, review and fix to a subagent.
disable-model-invocation: true
---

# Orchestrate a milestone

You oversee the build of the milestone tickets the dev names, and you write no code yourself. Every implementation, review and fix runs in a subagent, one at a time, from a brief you fill in from this folder's `briefs/`. Your jobs are a clean commit history and keeping the dev the decision-maker: anything the tickets and live docs leave open goes to the dev in chat, batched in your final report.

## Setup

1. **Scope.** Read the milestone's parent with `gh issue view <parent> --comments` and list its sub-issues with `gh api repos/Z-Aether/ribcage/issues/<parent>/sub_issues`. The scope is the tickets the dev named, taken in frontier order (`docs/agents/issue-tracker.md`).
2. **Base.** Check the tree is clean and note `git rev-parse HEAD`.
3. **Workspace.** `tmp/m<n>/` holds the drafted ticket comments, the reviews, and `handoff.md`: notes for later tickets, under each one's number.

## Per ticket

Take the tickets one at a time, even where they could run in parallel.

1. **Implement.** Fill in `briefs/implement.md` and spawn the agent.
   - **Model:** Sonnet for a small or mechanical ticket, Opus otherwise.
   - **Effort:** medium, or high only where a direction changes and needs redesign.

   Done when it reports its commits and a passing suite, and `git status` is clean.
2. **Review.** Fill in `briefs/review.md` and spawn an Opus agent. A change of only comments or docs skips the review.
3. **Fix loop.** While a review reports findings:
   - **Fix.** Fill in `briefs/fix.md` with every finding verbatim. Spawn Sonnet, or Opus when a finding needs redesign. It commits with `--fixup=<the ticket's commit>`.
   - **Re-review.** Fill in `briefs/re-review.md` and spawn a Sonnet agent.

   Done when a re-review comes back clean.
4. **Squash.** Run `before=$(git rev-parse HEAD^{tree}); GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <the ticket's base>`, then compare `git rev-parse HEAD^{tree}` with `$before`. Done when the trees match and `git log` shows no `fixup!` commit.
5. **Hand off.** Anything this build decided that a later ticket needs goes into `handoff.md`, under that ticket's number. Copy those lines into that ticket's implement brief.

**A usage limit** cuts an agent off mid-run. After the reset, resume it with SendMessage: it checks `git status` and `git log <base>..HEAD`, then finishes its brief.

## Wrap-up

Report to the dev:

- each ticket's commits and what it built;
- the decisions made during the build, from the drafts in `tmp/m<n>/`;
- the handoff notes for tickets outside the scope;
- the questions, numbered and in full.

Then, on the dev's word:

- push;
- post each drafted comment on its ticket, and each handoff note on its target ticket, or on that milestone's parent for a later milestone;
- close the finished tickets.

## Rules

- **Fix every finding, and drop everything else.** A review reports only what can cause a problem (`ticket-review`), and the fix loop fixes all of it. A remark that can't cause a problem is ignored for good. It gets no fix, no handoff note, no later pass and no line in your report.
- **Questions go to the dev in chat**, never on a ticket. Subagents make the choice most consistent with the docs and list it as a question, and you batch those questions into the wrap-up.
- **Map #4 and its design tickets are frozen.** A decision made during the build goes on the milestone ticket and into the live docs.
- **You alone post on GitHub.** Subagents draft into `tmp/m<n>/`, and you post at the wrap-up.
- **Push only on the dev's explicit word** (`CLAUDE.md`).
