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

Top-level directories sort by what a thing is, not by which ticket made it. A new kind of thing gets its directory and its line here.

- `ribcage/` is the Django project: settings and URLs, plus an app per module of `docs/design.md` §9, except Operations, whose `operations` is a plain package, and three apps outside it, and a few top-level modules.
  - `identity` holds `Voter`, the user model, and login, log out, registration through the join code and password change (#70, #72, #73). Its `backoff` slows repeated failed logins under a key of the caller's choosing, a voter's display name for login (#71) and one key for the admin login. Its `admin_session` is the admin's sign-in, a session row under a cookie of its own beside the voter's, and `admin_required`, the admin wall that sends anyone without it to the admin login (#76). Its `removal` holds `remove`, removal's one routine, and beside it `what_goes`, what the Roster tab's confirm lists as going; later milestones extend the two together (#79). Its `reset` gives a voter a generated password and sets `must_change_password`; until they set their own, `forced_change`'s middleware sends their every voter request to the one view marked `reachable_before_the_change`, the change form (#80).
  - `phase` holds the phase history, `PhaseMove`, and its interface in `history`: `current()`, `last_entered()` and `move()`, the one way the phase moves, which refuses a caller whose phase is stale (#74, #77). `order` is the pure part: the five phases in order and `neighbours`. Its views are the phase page at `/`, one template per phase, and Welcome at `/welcome/`, which registration opens with a one-shot session flag and which sends anyone else to the phase page (#75). Its `check` is the phase check: a voter write declares its phases with `phase_window(...)`, and a post from outside them writes nothing and reloads the tab onto the phase page; log out and change password carry `account_action` instead, and work in every phase. `tests/http/test_phase_check.py` sends every voter route a POST, PUT, PATCH and DELETE and fails any route that answers one with something other than 405 unless it carries `phase_window` or `account_action`; a voter page that only reads carries `require_safe` (#78).
  - `console` is the admin console: `/console/` opens the tab for the phase's work, and each tab, Phase · Films · Pick · Roster · Backup, is a view of its own behind `admin_required` (#28, #76, #86). Its `moves` holds what the Phase tab prints for each move, the act and its consequences, where later milestones add their sentences (#77). The Backup tab, `/console/backup/`, serves a backup, or takes one back, for a one-time code that its `backupcode` command makes in the `ribcage` container (#68, #81). Its `uploads` holds the upload handler that stops any request's file at the backup cap and drops it, so it is never read whole (#81).
  - `films` holds `Film` and `FilmCard`, the plain data the shared components and the models meet at, and `corpus`, the pure reader of the recorded seed corpus (#57).
  - `suggestions` is §9's Suggestions, notes, approval, and holds the films as they were suggested, since each film is one suggestion. `Suggestion` keeps a film's metadata as fetched, never refreshed, its runtime beside TMDB's, its approval, and its suggester's name for after their removal; `Suggestion.objects.suggest` is the one way a film enters the pool. `Note` is one per voter per suggestion, and the suggester's is the pitch. Its `pool` binds both to `FilmCard`s, newest first, for the SUGGEST and APPROVE pages (#26, #87).
  - `seeding` holds the dev-only seed commands, the only route to development data. Each milestone extends them to seed what it builds, and `--phase` picks the phase to seed into, writing the history that walks there (#25, #50, #74). Its `fetchcorpus` is the one command that goes online: it refetches the seed corpus into `fixtures/films/`, replacing the last fetch, and needs real `TMDB_API_KEY` and `DTDD_API_KEY` values (#57).
  - `gallery` is the dev-only visual reference: the theme and every shared component on corpus films, with sample voters and notes written for it. It answers only with `DEBUG` on, and each milestone adds the components it builds (#58).
  - `operations` is the plain package for §9's Operations module: the backup sidecar, run as `python -m ribcage.operations.backup` (`--help` lists its commands), and `offer`, the backup page's one offer, kept with its code's hash in `backup-offer/` beside the database and never in it (#68). An accepted upload lands beside the database too, under a backup's name, for the sidecar's `restore <name> --backups /data` (#81). It never loads the settings, so the sidecar is handed no secrets (#53).
  - `csrf.py` is the CSRF refusal, Django's `CSRF_FAILURE_VIEW`: a post whose token is stale or missing, as a login in another tab leaves every other tab's, reloads its tab onto the path of a Referer on this host, else `/`, writing nothing; a failed Origin or Referer check keeps Django's 403. `reload.py` is the reload it shares with the phase check: a redirect for a plain post, `HX-Redirect` for htmx (#76, #78).
  - Every page extends `templates/base.html`, which gives it the footer and the voter header, hands htmx the page's CSRF token, and wears the voter skin unless its `skin` block names admin or run. An admin page extends `console/page.html`, which swaps the console header in for the voter's (#76). Every route is public, voter or admin by the marks on its view, which `tests/http/routes.py` reads and `tests/http/test_route_kinds.py` holds to each kind's wall (#76). `as_it_is_now.py` reads the same marks, so the shell sends each voter and admin page, and no public one, with `Cache-Control: no-store` and `static/shell/as-it-is-now.js`, which reloads it when the back/forward cache restores it, as Chromium does even for `no-store`: Back and Forward show the page as it is now (#84). Login keeps Django's own never-cache header. A public page carries `login_not_required` and no `admin_required`, is held to zero queries, and swaps `components/public_header.html` into the `header` block, the wordmark home without the name menu, since naming the voter reads the session (#83; the admin login empties the block and keeps its own wordmark), and overrides the `footer` block without the abuse `mailto:`, which stays behind the login wall (#73).
  - `privacy.md` is the public privacy policy's one copy, rendered at `/privacy/` (#16, #49).
  - Shared components are templates in `templates/components/` over plain data, with their scripts in `static/components/` and their styles in `static/theme/theme.css` (#58).
  - `static/vendor/` holds the front-end libraries and TMDB's logo byte for byte, with their licences or terms, and its `vendored.toml` records each one's source, version or date, and checksum, and says how to upgrade one (#14, #46, #73).
  - `static/shell/` holds the base template's own scripts (#84).
  - `static/console/` holds the console tabs' own scripts (#85).
- `tests/` is pytest. `tests/pure/` holds plain-data tests, where any database access fails the test; `tests/http/` holds tests through Django's test client (#25), and tests against the test database that need no client; `tests/commands/` runs management commands, in process against the test database or as child processes to test startup and concurrency, and holds the tests that need a database file of their own: the backup module, SQLite's WAL behaviour, a migration over a database already holding voters and the phase-move race (`test_phase_race.py`), against temporary files. `tests/image/` needs Docker running and is all slow: `test_build_context.py` exports the filtered build context, and the rest build `ribcage:pytest` and run it alone and as the compose stack.
- `docs/` is prose. `docs/deferred/` holds designs that were worked out and then shelved. `docs/agents/` holds agent guides and skill configuration, each reached through a pointer in this file. `docs/runbook.md` holds the steps for running a window: the rebuild, taking, pulling and restoring a backup, and the teardown (#53, #55). `docs/theme.md` is the theme's guide (#58).
- `Dockerfile` builds the one image the host runs. Its `.dockerignore` is an allowlist, so a file the app needs at runtime outside `ribcage/` joins it there, and `tests/image/test_build_context.py` too (#40, #51).
- `compose.yaml` is the stack Komodo runs: the image at a pinned tag, the database on the `data` volume, published on the host's port 8080, where the host's proxy forwards (#54), and the `backup` sidecar on the same pin, writing a nightly backup to the `backups` volume (#53). `compose.local.yaml` layers a local build over it and moves the port to 8000 (#40, #52).
- `fixtures/` is recorded data, grouped by subject, that tests and seeding read offline. It holds data only. `films/` is the seed corpus: `corpus.json` lists the fifty films, with the TMDB id a person picked for each one not hand-entered, and `tmdb/` and `dtdd/` hold their payloads; `results.json` and `past_movies.txt` are #19's coverage measurement, kept as measured. DoesTheDogDie's raw output, `dtdd/` and `films/dtdd/`, is gitignored under DTDD's terms, so a fresh clone lacks it and pure tests never read it (#40, #57).
- `tools/` holds standalone harnesses from research tickets, one directory each. They stay outside the app and never ship.
- `scripts/` holds the dev's Git Bash scripts for running the deployment. `release.sh` is the runbook's rebuild through the re-pin in one run (#59).
- `private/` holds credentials and the group's real data, backups pulled from a stack among them, in `private/backups/` (#30). Its contents stay on this machine, out of commits, tickets and logs.
- `tmp/` is scratch, and nothing durable points into it.
- `staticfiles/` is `collectstatic`'s output, which WhiteNoise serves when `DEBUG` is off. It is rebuilt rather than edited.

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
- **Test:** `python -m pytest` runs every suite; `python -m pytest tests/pure`, `tests/http` or `tests/commands` runs one. The suite runs under `tests.settings`, which reads `.env.example`'s placeholders rather than `.env`.
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
