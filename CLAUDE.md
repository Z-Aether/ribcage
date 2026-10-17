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

- `ribcage/` is the Django project: settings and URLs, plus one app per module of `docs/design.md` §9 and two outside it.
  - `identity` holds `Voter`, the user model.
  - `hello` is M1 scaffolding that M3 removes (#42, #47).
  - `seeding` holds the dev-only seed commands, the only route to development data. Each milestone extends them to seed what it builds, and `--phase` picks which of the phases M3 adds to seed into (#25, #50).
  - Every page extends `templates/base.html`. A page outside the login wall carries `login_not_required`, which is how `tests/http/test_public_pages.py` finds it and holds it to zero queries.
  - `privacy.md` is the public privacy policy's one copy, rendered at `/privacy/` (#16, #49).
  - `static/vendor/` holds the front-end libraries byte for byte with their licences, and its `vendored.toml` records each one's source, version and checksum and says how to upgrade one (#14, #46).
- `tests/` is pytest. `tests/pure/` holds plain-data tests, where any database access fails the test; `tests/http/` holds tests through Django's test client (#25); `tests/commands/` runs management commands: in process against the test database, or as a child process to test startup. `tests/image/` builds the container image and runs it, alone and as the compose stack, so every test there is slow and needs Docker running.
- `docs/` is prose. `docs/deferred/` holds designs that were worked out and then shelved. `docs/agents/` holds agent guides and skill configuration, each reached through a pointer in this file.
- `fixtures/` is recorded data, grouped by subject, that tests and seeding read offline. It holds data only.
- `tools/` holds standalone harnesses from research tickets, one directory each. They stay outside the app and never ship.
- `private/` holds credentials and the group's real data. Its contents stay on this machine, out of commits, tickets and logs.
- `tmp/` is scratch, and nothing durable points into it.
- `Dockerfile` builds the one image the host runs. Its `.dockerignore` is an allowlist, so a file the app needs at runtime outside `ribcage/` joins it there, and `tests/image/test_build_context.py` too (#40, #51).
- `compose.yaml` is the stack Komodo runs: the image at a pinned tag, the database on the `data` volume, joined to the host's proxy network and publishing no port. `compose.local.yaml` layers a loopback port and a network of its own over it for local runs (#40, #52).
- `staticfiles/` is `collectstatic`'s output, which WhiteNoise serves when `DEBUG` is off. It is rebuilt rather than edited.

**Ignored files are part of the layout.** `private/`, `tmp/`, `staticfiles/` and some of `fixtures/` are gitignored, so `git ls-files` won't show them. Check `.gitignore` before concluding a file is missing.

## Running it

Python 3.14, with every dependency pinned exactly in `requirements.txt` (the app) and `requirements-dev.txt` (plus the test harness). Changing a dependency means re-pinning it and its transitive dependencies there.

- **Install:** `py -3.14 -m venv .venv`, then `.venv/Scripts/python -m pip install -r requirements-dev.txt` (off Windows, `python3.14` and `.venv/bin/python`). The commands below use the venv's `python`.
- **Configure:** copy `.env.example` to `.env` (gitignored). Settings come only from the environment; `manage.py` alone reads `.env`, filling in what the environment lacks (#45). `.env.example` lists every variable, so a new one goes there too and, unless only Compose reads it like `PROXY_NETWORK`, into `compose.yaml`'s `environment`, a new required variable (one with no default) also joins the Dockerfile's `collectstatic` line, and a new judgement constant also joins the block at the foot of `ribcage/settings.py` and `JUDGEMENT_DEFAULTS` in `tests/pure/test_settings.py`, which pins its ticket's default.
- **Run the server:** `python manage.py migrate`, then `python manage.py runserver`. The local database is `db.sqlite3`, gitignored. With `DEBUG` off, run `python manage.py collectstatic` first.
- **Browse it** at `localhost` or `127.0.0.1` in Chromium or Firefox, Playwright's Chromium included: only they keep the always-`Secure` cookies over plain http, so from other browsers or a LAN address every POST gets a 403 (#31).
- **Seeded instance:** `python manage.py seededserver` rebuilds the local database from nothing with known voters and serves it at `http://127.0.0.1:8000/`; `python manage.py seed` only rebuilds. Both refuse unless `DEBUG` is on, which the deployment never sets (#50).
- **Verify a page in a browser** by following `docs/agents/browser-verification.md`: Playwright over MCP against the seeded instance, at desktop width and at 390 px (#25).
- **Test:** `python -m pytest` runs every suite; `python -m pytest tests/pure`, `tests/http` or `tests/commands` runs one. The suite runs under `tests.settings`, which reads `.env.example`'s placeholders rather than `.env`.
- **Slow tests** are marked `@pytest.mark.slow` and stay out of the default run: `python -m pytest -m slow` runs only them, `-m ""` runs everything. Use the mark for on-demand checks such as #6's enumeration oracle.
- **Build the image** from a clean, committed tree: `docker build --pull --platform linux/amd64 -t ribcage:<tag> .`, then `python -m pytest tests/image -m slow`. The tag is the UTC build minute and the commit, `$(date -u +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)`; `-t` keeps builds off `latest` and the stack's pin keeps deploys off it (#40). The image serves plain HTTP on port 8000, the port the host's proxy forwards to (#43). It starts only with every variable set (`docker run --env-file`), migrates, then starts gunicorn with the flags in `ribcage/gunicorn_conf.py`. The app writes only under `/data`, where `DATABASE_PATH` points (#51, #52).
- **Run the stack** locally: `docker compose -f compose.yaml -f compose.local.yaml up --build` builds the working tree as `ribcage:local` and serves it at `http://127.0.0.1:8000/`, runserver's port. Compose fills `compose.yaml`'s placeholders from `.env`, `PROXY_NETWORK` included, and a variable set in the shell wins over it. `down` keeps the database on its volume and `down -v` deletes it (#52).

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
