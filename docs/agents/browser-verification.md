# Verifying in a browser

How an agent checks a page by driving the seeded local instance with Playwright over MCP (#25). The walk shows what is in the DOM, what the console reports and how the layout holds at desktop width and at 390 px. It is blind to the proxy: with DEBUG on, the app takes requests as plain HTTP, so CSRF and HSTS failures show only on the real deployment (#16, #25, #54).

## Before you start

- **The tools are `mcp__playwright__*`.** When they are deferred, load them with ToolSearch `+playwright browser`. The server is registered in the dev's private local scope, outside the repo. When the tools are missing, stop and report it: Claude in Chrome and other browsers are kept for debugging the real deployment (#25).
- **Install and `.env`** as `CLAUDE.md`'s *Running it* says, with `DEBUG=true`, the value `.env.example` carries. The seed refuses to run without it.

## Steps

1. **Seed and start.** Run `scripts/seeded.sh start`, a plain foreground call. It stops any seeded server already running, then runs `manage.py seededserver` in the background, which rebuilds the database at `DATABASE_PATH` from nothing, the dev's local data included, and serves `http://127.0.0.1:8000/` without autoreload. The script returns once the server answers, printing the seeded voters and their password. Options pass through to `seededserver`: `--phase` picks the phase to seed, one of the five (#25, #74), and `/` then shows that phase's page. To pick up a code change or a fresh seed, run `start` again.
2. **Drive.** Navigate to `http://127.0.0.1:8000/…`: every cookie is `Secure`, so only a loopback address keeps them (#31). Assert on `browser_snapshot`, the accessibility tree, and act with its refs. Voter pages are behind the login wall, so log in at `/login/` as any seeded voter, filling `#id_username` and `#id_password` with a name and the password `start` printed. Admin pages, under `/console/`, are behind the admin login at `/console/login/`, filling `#id_password` with `ADMIN_PASSWORD` from `.env`; one context holds both sessions at once (#76). The MCP holds one browser context, so a check needing two voters signed in at once needs a plain Playwright script (#25).
3. **Check every page at both widths.** Take each page at the default 1280×720, then `browser_resize` to 390×844, then resize back before the next page. At each width, snapshot, then `browser_take_screenshot` with the filename `tmp/<ticket>-<page>-desktop.png` or `tmp/<ticket>-<page>-390.png`. A relative filename is taken from the repo root, so a bare one lands untracked beside `CLAUDE.md`; confirm the path the tool reports starts with `tmp`.
   - **Frame each state the change touches.** Pass the element's ref to `browser_take_screenshot` so it fills the frame. A shot of the page's top can leave a card lower down off-screen.
   - **Compare across an action.** Where an action swaps part of the page, as an htmx save, a refusal, or opening or closing a card does, screenshot the same element before and after at each width. A control that moves, wraps or resizes across the swap is a finding.

   Read each screenshot for overflow, overlap, shifts and illegible text. Screenshots are evidence for this check alone, never baselines and never committed (#25). Done when every page and touched state in scope has its screenshots at both widths and you have read each one.
4. **Read the console.** After the walk, call `browser_console_messages` with level `error` and `all` set, and expect it empty. Read the server's log, `tmp/seededserver.log`, for tracebacks too.
5. **Stop the server, and leave the browser open.** The browser is in-memory (`--isolated`) and goes with the session; `browser_close` hangs, so leave it uncalled. Run `scripts/seeded.sh stop`, which kills the server's process tree and returns once it no longer answers. Done when it prints `Stopped.`
6. **Report** each page at each width: what you did, what the snapshot showed, the console errors, and the screenshot filenames.
