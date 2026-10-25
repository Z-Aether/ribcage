# Ribcage

A web app a group of friends uses to plan and run one film marathon. It is rebuilt for each marathon and torn down afterwards. The repo is public.

**Keep this file true.** When you deliberately change the repo so that a line here no longer holds, update that line in the same commit, editing with the `writing-for-agents` skill.

## Finding things

- **Words** mean what `GLOSSARY.md` says they mean. Use its terms in code, tests and tickets, identifiers included.
- **What** gets built is in `docs/design.md`, and **in what order** is in `docs/milestones.md`. They are the live docs: a decision made during the build changes their lines in the same commit, citing the ticket that made it.
- **Work to do** lives on milestone tickets: one parent per milestone, all ten created up front as baselines, its implementation tickets as sub-issues wired with native blocking edges. Detail decided ahead of its milestone goes on that milestone's parent, or on a sub-issue opened early. See `docs/agents/issue-tracker.md`.
- **Why** something is the way it is: look up the ticket cited beside it (`#n`, read with `gh issue view <n> --comments`). The ticket is the decision of record, and its last dated amendment wins.
- **The design record** is map #4 and the design tickets it links. It is frozen: read it for the reasoning behind a design decision, and record anything that supersedes it on a milestone ticket and in the live docs.
- **How it looks**, and why: `docs/theme.md`, read before building or styling any page. The gallery shows it.
- **Prototypes and research write-ups** live on branches: `prototype/<screen>` and `research/<topic>`; `prototype/theme` keeps the theme directions set aside (#58). The ticket that produced one names its branch. Read them with `git show <branch>:<path>`.

## Layout

Top-level directories sort by what a thing is, not by which ticket made it.

**This section is a map, not a catalogue.** Each line names a directory or app and what it holds, then only what an agent would get wrong from the code alone: the one routine a kind of change must go through, a convention a test enforces, a gotcha no file confesses. A module's interface, routes and behaviour live in its code, its ticket and `docs/design.md`, where grep finds them. A change edits this section when it adds a new kind of thing or makes a line here untrue; a new module, view or route inside a listed app leaves it as it is.

- `ribcage/` is the Django project: settings, URLs and a few top-level modules, plus an app per module of `docs/design.md` §9, with three apps outside it and Operations as a plain package.
  - `identity`: voters, login, registration, passwords and the admin's sign-in, with `admin_required`, the admin wall (#76). Removing a voter goes through `removal.remove`, and the confirm lists `removal.what_goes`; later milestones extend the two together, what `on_delete` expresses staying there (#79, #98, #118).
  - `phase`: the phase history and the phase pages. `history.move()` is the one way the phase moves (#77). Every voter write declares its phases with `check.phase_window(...)`, or carries `account_action` to work in every phase, and `tests/http/test_phase_check.py` fails a route that carries neither (#78).
  - `console`: the admin console, a view per tab behind `admin_required` (#76). A phase move goes through `moves.make`, which pairs entering RUN with the trigger-data purge (#106).
  - `films`: `Film`, the film card's plain data, and the TMDB client (#57, #92).
  - `suggestions`: the pool, its notes and the *Suggest a film* flow. `Suggestion.objects.suggest` is the one way a film enters it. `withdrawal.withdrawable` is the one rule for whether anything downstream holds a film, and `with_holds` the one loader for it, which a suggestion loaded any other way fails; M7 and M9 extend the two together (#90, #97, #118).
  - `triggers`: DoesTheDogDie's client, each film's trigger data and the refresh after a phase move (#101, #104). `status.shown_counts` is the one rule for which topics a film lists and counts, on every surface (#103). `carrying.carries` is the one rule for a film carrying a topic, behind the ring, the tray and My warnings' films (#109). `matching.matched` is the one rule for a viewer's matched topics and whether they ring, over a watched list and a snapshot's counts; the admin's card gets none (#111). `watched.set_ticked` is the one write of a single tick, from My warnings and from the card's watch toggle, and refuses while *I don't care* is on, `watched.stop_caring` the one way the list is cleared, and `watched.does_not_care` reads for any surface that offers a tick (#107, #110, #114).
  - `ballot`: the ballot record, one per voter and film, and the done marker. A record left with no score, no veto and no seen it is deleted, so any record that exists holds its film; the hold reaches `withdrawable` through `with_holds`, and the record's key to `Suggestion` is `PROTECT` so a missed hold fails loud (#118). `placing.place` is the one way a score or a veto is set or cleared, and `placing.give_reason` the one write of a veto's reason, `order.shuffled` the one per-voter order every tile list takes, and `order.tray_order` puts matched films first in the tray alone (#119, #120).
  - `seeding`: the dev-only seed commands, the only route to development data, which each milestone extends to seed what it builds (#50, #87). `fetchcorpus` is the one command that goes online (#57).
  - `gallery`: the dev-only visual reference, which each milestone extends with the shared components it builds (#58).
  - `operations`: the backup sidecar, run as `python -m ribcage.operations.backup`. It never loads the settings, so the sidecar holds no secrets (#53).
  - Every route is public, voter or admin by the marks on its view, which `tests/http/routes.py` reads and `tests/http/test_route_kinds.py` holds to each kind's wall (#76). A voter or admin route that is no page the sweep reads (a POST-only act, or a GET that redirects) is listed in `routes.py`'s `FRAGMENTS` if it can answer with a card, its section or a topic, else in `NO_DTDD_DATA`; `tests/http/test_dtdd_credit.py` fails a route in neither, sweeps those and every page, and fails where DoesTheDogDie's data sits outside a `data-dtdd` region holding its own "Powered by DoesTheDogDie.com" link. A `part` fragment, swapped into a region its host page credits, is held to land in one (#112). The same pages and fragments are swept again by `tests/http/test_watched_privacy.py`, which renders them as another voter and as the admin with one voter's watched list ticked, empty and under *I don't care*, and fails on any difference; a surface that shows a voter's own choices (M6's ballot, M8's reveal) needs no listing beyond `routes.py`, and the shared sweep lives in `tests/http/sweeping.py` (#113). A public page carries `login_not_required`, is held to zero queries, and swaps in `components/public_header.html`, since naming the voter reads the session (#83).
  - Every page extends `templates/base.html`; an admin page extends `console/page.html` (#76). Shared components are templates in `templates/components/` over plain data, with their scripts in `static/components/` and their styles in `static/theme/theme.css` (#58). A surface's own scripts sit in `static/<surface>/`.
  - `static/vendor/` holds the front-end libraries byte for byte, and its `vendored.toml` records each one's source, version and checksum, and how to upgrade one (#14, #46).
- `tests/` is pytest, a suite per kind of test (#25):
  - `pure/`: plain-data tests, where any database access fails the test.
  - `http/`: tests through Django's test client, and tests against the test database that need no client. Its `conftest.py` makes TMDB and DoesTheDogDie unreachable, so a test that reaches either gives its client a fake transport (#92, #101).
  - `commands/`: management commands, in process or as child processes, and every test that needs a database file of its own, such as concurrency and migrations.
  - `image/`: needs Docker running and is all slow.
- `docs/` is prose: the live docs, `runbook.md` for running a window (#53, #55), `theme.md` (#58), `deferred/` for shelved designs, and `agents/` for agent guides, each reached through a pointer in this file.
- `Dockerfile` builds the one image the host runs. Its `.dockerignore` is an allowlist, so a file the app needs at runtime outside `ribcage/` joins it there, and `tests/image/test_build_context.py` too (#40, #51).
- `compose.yaml` is the stack Komodo runs, at a pinned tag, with the `backup` sidecar (#53, #54); `compose.local.yaml` layers a local build over it (#52).
- `fixtures/` is recorded data, grouped by subject, that tests and seeding read offline; `films/` is the seed corpus (#57). DoesTheDogDie's raw output is gitignored under its terms, so a fresh clone lacks it and pure tests never read it (#40).
- `tools/` holds standalone harnesses from research tickets, one directory each, outside the app.
- `.claude/skills/` holds the project's own skills, the only tracked ones; the rest are installed links into `.agents/`, gitignored.
- `scripts/` holds Git Bash scripts: the dev's `release.sh` (#59) and `seeded.sh`, which starts and stops the seeded instance for a browser check.
- `private/` holds credentials and the group's real data, pulled backups among them (#30). Its contents stay on this machine, out of commits, tickets and logs.
- `tmp/` is scratch, and nothing durable points into it.
- `staticfiles/` is `collectstatic`'s output, rebuilt rather than edited.

**Ignored files are part of the layout.** `private/`, `tmp/`, `staticfiles/` and some of `fixtures/` are gitignored, so `git ls-files` won't show them. Check `.gitignore` before concluding a file is missing.

## Running it

Python 3.14, with every dependency pinned exactly in `requirements.txt` (the app) and `requirements-dev.txt` (plus the test harness). Changing a dependency means re-pinning it and its transitive dependencies there.

- **Install:** `py -3.14 -m venv .venv`, then `.venv/Scripts/python -m pip install -r requirements-dev.txt` (off Windows, `python3.14` and `.venv/bin/python`). The commands below use the venv's `python`.
- **Configure:** copy `.env.example` to `.env` (gitignored). Settings come only from the environment; `manage.py` alone reads `.env`, filling in what the environment lacks (#45). `.env.example` lists every variable, so a new one goes there too. It also goes into the `ribcage` service's `environment` in `compose.yaml`. A new required variable, one with no default, also joins the Dockerfile's `collectstatic` line. A new judgement constant also joins the block at the foot of `ribcage/settings.py` and `JUDGEMENT_DEFAULTS` in `tests/pure/test_settings.py`, which pins its ticket's default.
- **Run the server:** `python manage.py migrate`, then `python manage.py runserver`. The local database is `db.sqlite3`, with the backup page's offer `backup-offer/` and its uploaded `backup-*.sqlite3` beside it, all gitignored. With `DEBUG` off, run `python manage.py collectstatic` first.
- **Browse it** at `localhost` or `127.0.0.1` in Chromium or Firefox, Playwright's Chromium included: only they keep the always-`Secure` cookies over plain http, so from other browsers or a LAN address every POST only reloads its page (#31, #76).
- **Seeded instance:** `python manage.py seededserver` rebuilds the local database from nothing with known voters and serves it at `http://127.0.0.1:8000/`; `python manage.py seed` only rebuilds. Both refuse unless `DEBUG` is on, which the deployment never sets (#50).
- **Gallery:** with the seeded instance running, open `http://127.0.0.1:8000/gallery/` and log in as any seeded voter (#58, #70).
- **Verify a page in a browser** by following `docs/agents/browser-verification.md`: Playwright over MCP against the seeded instance, at desktop width and at 390 px (#25).
- **Test:** `python -m pytest -n 4` runs every suite across four workers; `-n 0` runs it serially, for debugging. A targeted run, such as `python -m pytest tests/pure`, `tests/http`, `tests/commands` or a file, goes without `-n`. The suite runs under `tests.settings`, which reads `.env.example`'s placeholders rather than `.env`.
- **Slow tests** are marked `@pytest.mark.slow` and stay out of the default run: `python -m pytest -m slow` runs only them, `-m ""` runs everything. Use the mark for on-demand checks such as #6's enumeration oracle.
- **Build the image** with `scripts/release.sh "<what changed>" <ticket>`, from a clean tree already on `origin/main`. It builds, runs every suite, pushes the image under the registry path `compose.yaml`'s pin carries, re-pins `compose.yaml` to it in a commit, which is what the host runs, and leaves that image as the only local `ribcage` one. The tag is the UTC build minute and the commit, never `latest` (#40, #54, #59). `tests/image` builds its own `ribcage:pytest` from the working tree, so `python -m pytest tests/image -m slow` checks the Dockerfile and the stack, not a tagged build. `docker run --env-file` starts the image alone, given every required variable and a `DATABASE_PATH` under `/data`, the database volume's mount point; `.env.example`'s relative `db.sqlite3` resolves into `/app`, which the app cannot write (#51).
- **Run the stack** locally: `docker compose -f compose.yaml -f compose.local.yaml up --build` builds the working tree as `ribcage:local` and serves it at `http://127.0.0.1:8000/`, runserver's port. Compose fills `compose.yaml`'s placeholders from `.env`, and a variable set in the shell wins over it. `down` keeps the database and backups on their volumes and `down -v` deletes both (#52, #53).

## Commits

- **Commit freely; push only when the dev explicitly says to.** Everything after `@{u}` is still yours to rewrite: reorder, squash and fixup until each commit is one standalone feature or module, splitting a ticket across several commits where it holds several.
- **Messages are one short line.** An implementation commit ends with the ticket it resolves: `Add the phase check to VOTE (#34)`.
- **Code documents itself** through names. A comment is one short line telling a later agent about a non-obvious decision, citing its ticket where there is one.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues on `Z-Aether/ribcage`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its role name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repo root. Decisions are recorded on tickets rather than ADRs.
