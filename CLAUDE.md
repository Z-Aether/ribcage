# Ribcage

A web app a group of friends uses to plan and run one film marathon. It is rebuilt for each marathon and torn down afterwards. The repo is public.

**Keep this file true, cutting first.** When you deliberately change the repo so that a line here no longer holds, mend that line in the same commit, editing with the `writing-for-agents` skill. A line that went untrue was carrying detail its code already holds, so cut it back to what still holds before adding a word to it.

## Finding things

- **Words** mean what `GLOSSARY.md`, the one domain doc, says they mean. Use its terms in code, tests and tickets, identifiers included.
- **What** gets built is in `docs/design.md`, and **in what order** is in `docs/milestones.md`. They are the live docs: a decision made during the build changes their lines in the same commit, citing the ticket that made it.
- **Work to do** lives on milestone tickets in the issue tracker, GitHub issues on `Z-Aether/ribcage` through `gh`: a parent per milestone, its implementation tickets as sub-issues wired with native blocking edges. Read `docs/agents/issue-tracker.md` before creating, wiring or amending a ticket, or recording a decision on one.
- **Triage labels** are the five canonical triage roles, each label string equal to its role name: `docs/agents/triage-labels.md`.
- **Why** something is the way it is: look up the ticket cited beside it (`#n`, read with `gh issue view <n> --json title,body,comments --jq '.title, .body, .comments[].body'`). The ticket is the decision of record, in place of an ADR, and its last dated amendment wins.
- **The design record** is map #4 and the design tickets it links. It is frozen: read it for the reasoning behind a design decision, and record anything that supersedes it on a milestone ticket and in the live docs.
- **How it looks**, and why: `docs/theme.md`, read before building or styling any page. The gallery shows it.
- **Prototypes and research write-ups** live on branches: `prototype/<screen>` and `research/<topic>`; `prototype/theme` keeps the theme directions set aside (#58). The ticket that produced one names its branch. Read them with `git show <branch>:<path>`.

## Layout

Top-level directories sort by what a thing is, not by which ticket made it.

**This section is a map.** A line names a directory or app and says what it holds, in words wide enough that work inside it leaves the line true. After that it carries only what a change made elsewhere must **join** there: a list, a sweep or a pair of functions that a new route, model, module or file has to be added to, which nothing in the code being written points to. How an app does its own work (its one write, its one loader, its one rule) is said by the docstring of the module that owns it, where whoever calls or edits it reads it: put it there. So a ticket built inside a listed app leaves this section as it was, and a line here changes when a directory or app is added, or a thing to join is.

- `ribcage/` is the Django project: settings, URLs and a few top-level modules, plus an app per module of `docs/design.md` §9, with three apps outside it and Operations, Readouts and Solver as plain packages.
  - `identity`: voters, login, registration, passwords and the admin's sign-in, with the login wall and `admin_required`, the admin wall (#76). New data that hangs on a voter joins `removal.what_goes`, the confirm's list, and `removal.remove` where `on_delete` alone can't say how it goes (#79, #98, #118).
  - `phase`: the phase history, the phase check and the phase pages (#77, #78).
  - `console`: the admin console, a view per tab behind `admin_required` (#76).
  - `films`: `Film`, the film card's plain data, and the TMDB client (#57, #92).
  - `suggestions`: the pool, its notes, the *Suggest a film* flow and the card's *Save*. Anything new that holds a film joins `withdrawal.with_holds` and `withdrawable` together, its key to `Suggestion` `PROTECT` so a missed hold fails loud (#90, #118, #151).
  - `triggers`: DoesTheDogDie's client, each film's trigger data, the watched list, and the rules for the topics a film carries and a viewer matches (#101, #103, #107, #111).
  - `ballot`: the ballot record, the done marker, the ballot's board and the reveal's matrix (#118, #119, #154).
  - `timetable`: the timetable, its boxes and the pure `engine` over plain boxes, the track and the evening drawn from them, and the loaders behind Compare, `plan` and `batch` (#135, #136, #155, #164, #165).
  - `shortlist`: the kept proposals, each a film set and its provenance as plain text (#169).
  - `solver`: SOLVE's pure core, a plain package with no app and no database: the `Problem`, its objective and the HiGHS model (#165). A new input to a solve joins `Problem` or the settings `timetable.batch.fingerprint` reads, and a new module a solve runs on joins `timetable.batch.solver_sources`, so the slates Compare holds in the admin's session end when either changes (#166).
  - `readouts`: plain functions over plain data, no app and no database: film points, the floor set, the tiebreaker and every readout Compare, the Roster and the track show, each loaded from the database by an app, as `ballot.floor` and `timetable.plan` do (#137, #146, #164).
  - `seeding`: the dev-only seed commands, the only route to development data, which each milestone extends to seed what it builds (#50, #87). `fetchcorpus` is the one command that goes online (#57).
  - `gallery`: the dev-only visual reference, which each milestone extends with the shared components it builds (#58).
  - `operations`: the backup sidecar, run as `python -m ribcage.operations.backup`. It never loads the settings, so the sidecar holds no secrets (#53).
  - Every route is public, voter or admin by the marks on its view, which `tests/http/routes.py` reads and `tests/http/test_route_kinds.py` holds to each kind's wall (#76). A voter write also declares its phases with `phase.check.phase_window(...)`, or carries `account_action` to work in every phase, and `tests/http/test_phase_check.py` fails one that carries neither (#78). A voter or admin route that is no page the sweep reads (a POST-only act, or a GET that redirects) joins `routes.py`'s `FRAGMENTS` if it can answer with a card, its section or a topic, else `NO_DTDD_DATA`. Two tests sweep those and every page: `test_dtdd_credit.py` fails a route in neither list, and fails where DoesTheDogDie's data sits outside a `data-dtdd` region holding its own "Powered by DoesTheDogDie.com" link (#112); `test_watched_privacy.py` renders them as another voter and as the admin, and fails where one voter's watched list changes anything (#113). A public page carries `login_not_required`, is held to zero queries, and swaps in `components/public_header.html`, since naming the voter reads the session (#83).
  - Every page extends `templates/base.html`; an admin page extends `console/page.html` (#76). Shared components are templates in `templates/components/` over plain data, with their scripts in `static/components/` and their styles in `static/theme/theme.css` (#58). A surface's own scripts sit in `static/<surface>/`.
  - `static/vendor/` holds the front-end libraries byte for byte, and its `vendored.toml` records each one's source, version and checksum, and how to upgrade one (#14, #46).
- `tests/` is pytest, a suite per kind of test (#25), with two harnesses run as modules beside them, `oracle.py` and `tuning.py` (#173, #174):
  - `pure/`: plain-data tests, where any database access fails the test.
  - `http/`: tests through Django's test client, and tests against the test database that need no client. Its `conftest.py` makes TMDB and DoesTheDogDie unreachable, so a test that reaches either gives its client a fake transport (#92, #101).
  - `commands/`: management commands, in process or as child processes, and every test that needs a database file of its own, such as concurrency and migrations.
  - `image/`: needs Docker running and is all slow.
  - **A test is owed** for a rule, a wall or a write: what a function computes, who a route lets in and in which phase, what a POST stores or refuses. Looks, markup, layout and in-browser behaviour are proved by the browser check, as is what the seed data and the gallery hold, and `pure/test_no_source_pins.py` fails a test that reads shipped JS, CSS or template source.
- `docs/` is prose: the live docs, `runbook.md` for running a window (#53, #55), `theme.md` (#58), `deferred/` for shelved designs, and `agents/` for agent guides, each reached through a pointer in this file.
- `Dockerfile` builds the one image the host runs. Its `.dockerignore` is an allowlist, so a file the app needs at runtime outside `ribcage/` joins it there, and `tests/image/test_build_context.py` too (#40, #51).
- `compose.yaml` is the stack Komodo runs, at a pinned tag, with the `backup` sidecar (#53, #54); `compose.local.yaml` layers a local build over it (#52).
- `fixtures/` is recorded data, grouped by subject, that tests and seeding read offline; `films/` is the seed corpus (#57). DoesTheDogDie's raw output is gitignored under its terms, so a fresh clone lacks it and pure tests never read it (#40). `solver/cases.json` is generated by `tests/oracle.py`: regenerate it only when the objective or a hand-chosen case changes on purpose, and say which in the commit (#173).
- `tools/` holds standalone harnesses from research tickets, one directory each, outside the app.
- `.claude/skills/` holds the project's own skills, the only tracked ones; the rest are installed links into `.agents/`, gitignored.
- `scripts/` holds Git Bash scripts: the dev's `release.sh` (#59) and `seeded.sh`, which starts and stops the seeded instance for a browser check.
- `private/` holds credentials and the group's real data, pulled backups among them (#30). Its contents stay on this machine, out of commits, tickets and logs.
- `tmp/` is scratch, and nothing durable points into it.
- `staticfiles/` is `collectstatic`'s output, rebuilt rather than edited.

**Ignored files are part of the layout.** `private/`, `tmp/`, `staticfiles/` and some of `fixtures/` are gitignored, so `git ls-files` won't show them. Check `.gitignore` before concluding a file is missing.

## Running it

Python 3.14, with every dependency pinned exactly in `requirements.txt` (the app) and `requirements-dev.txt` (plus the test harness). Changing a dependency means re-pinning it and its transitive dependencies there.

- **Install:** `py -3.14 -m venv .venv`, then `.venv/Scripts/python -m pip install -r requirements-dev.txt` (off Windows, `python3.14` and `.venv/bin/python`). The commands below name it, since the system `python` lacks the dependencies.
- **Configure:** copy `.env.example` to `.env` (gitignored). Settings come only from the environment; `manage.py` alone reads `.env`, filling in what the environment lacks (#45). A new variable joins `.env.example`, which lists every one, and the `ribcage` service's `environment` in `compose.yaml`. One with no default also joins the Dockerfile's `collectstatic` line. A judgement constant also joins the block at the foot of `ribcage/settings.py` and `JUDGEMENT_DEFAULTS` in `tests/pure/test_settings.py`, which pins its ticket's default.
- **Run the server:** `.venv/Scripts/python manage.py migrate`, then `.venv/Scripts/python manage.py runserver`. The local database is `db.sqlite3`, gitignored with the backup page's files beside it. With `DEBUG` off, run `.venv/Scripts/python manage.py collectstatic` first.
- **Browse it** at `localhost` or `127.0.0.1` in Chromium or Firefox, Playwright's Chromium included: only they keep the always-`Secure` cookies over plain http, so from other browsers or a LAN address every POST only reloads its page (#31, #76).
- **Seeded instance:** `.venv/Scripts/python manage.py seededserver` rebuilds the local database from nothing with known voters and serves it at `http://127.0.0.1:8000/`; `.venv/Scripts/python manage.py seed` only rebuilds. Both refuse unless `DEBUG` is on, which the deployment never sets (#50).
- **Gallery:** with the seeded instance running, open `http://127.0.0.1:8000/gallery/` and log in as any seeded voter (#58, #70).
- **Verify a page in a browser** by following `docs/agents/browser-verification.md`: Playwright over MCP against the seeded instance, at desktop width and at 390 px (#25).
- **Test:** `.venv/Scripts/python -m pytest -n 4` runs every suite across four workers; `-n 0` runs it serially, for debugging. A targeted run, such as `.venv/Scripts/python -m pytest tests/pure`, `tests/http`, `tests/commands` or a file, goes without `-n`. The suite runs under `tests.settings`, which reads `.env.example`'s placeholders rather than `.env`.
- **Light run:** `.venv/Scripts/python -m pytest -n 4 -m "not slow and not heavy"` leaves out the tests marked `heavy`, a twentieth of the tests and half the run's time: grep `mark.heavy` for them, and `tests/commands/conftest.py` marks its whole suite. A ticket's implementer ends on the light run, and the full run belongs to the batch's end (`orchestrate-milestone`) and to `release.sh`. Mark a test heavy when it takes whole seconds and few changes touch what it guards; a heavy file run by name still runs.
- **Slow tests** are marked `@pytest.mark.slow` and stay out of the default run: `.venv/Scripts/python -m pytest -m slow` runs only them, `-m ""` runs everything. Use the mark for on-demand checks such as #6's enumeration oracle.
- **Build the image** with `scripts/release.sh "<what changed>" <ticket>`, from a clean tree already on `origin/main`. It builds, runs every suite, pushes the image, re-pins `compose.yaml` to it in a commit, which is what the host runs, and removes every other local `ribcage` image. The tag is the UTC build minute and the commit, never `latest` (#40, #54, #59). `tests/image` builds its own `ribcage:pytest` from the working tree, so `.venv/Scripts/python -m pytest tests/image -m slow` checks the Dockerfile and the stack, not a tagged build. `docker run --env-file` starts the image alone, given every required variable and a `DATABASE_PATH` under `/data`, the database volume's mount point; `.env.example`'s relative `db.sqlite3` resolves into `/app`, which the app cannot write (#51).
- **Run the stack** locally: `docker compose -f compose.yaml -f compose.local.yaml up --build` builds the working tree as `ribcage:local` and serves it at `http://127.0.0.1:8000/`, runserver's port. Compose fills `compose.yaml`'s placeholders from `.env`, and a variable set in the shell wins over it. `down` keeps the database and backups on their volumes and `down -v` deletes both (#52, #53).

## Commits

- **Commit freely; push only when the dev explicitly says to.** Everything after `@{u}` is still yours to rewrite: reorder, squash and fixup until each commit is one standalone feature or module, splitting a ticket across several commits where it holds several.
- **Messages are one short line.** An implementation commit ends with the ticket it resolves: `Add the phase check to VOTE (#34)`.
- **Code documents itself** through names. A comment is one short line telling a later agent about a non-obvious decision, citing its ticket where there is one.
