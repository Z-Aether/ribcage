Re-review fixes to ticket #{n}, "{title}", a sub-issue of milestone M{m} (#{parent}), in the Ribcage repo (C:\Ribcage_main, a Django app; Windows, Git Bash available). Run the `ticket-review` skill's re-review over `{ticket_sha}..HEAD`, the fixup commits.

- The findings they answer are in review {k}'s report, `tmp/m{m}/{n}-review-{k}.md`.
- The fixer's report is `tmp/m{m}/{n}-fix-{k}.md`.

Write your report to `tmp/m{m}/{n}-review-{k+1}.md`. Return the verdict, one line per finding with its grade, and the design questions in full.
