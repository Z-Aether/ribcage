# Verifying in a browser

How an agent checks a page by driving the seeded local instance with Playwright over MCP (#25). The walk shows what is in the DOM, what the console reports and how the layout holds at desktop width and at 390 px. It is blind to the proxy: with DEBUG on, the app takes requests as plain HTTP, so CSRF and HSTS failures show only on the real deployment (#16, #25, #54).

## Before you start

- **The tools are `mcp__playwright__*`.** When they are deferred, load them with ToolSearch `+playwright browser`. The server is registered in the dev's private local scope, outside the repo. When the tools are missing, stop and report it: Claude in Chrome and other browsers are kept for debugging the real deployment (#25).
- **Install and `.env`** as `CLAUDE.md`'s *Running it* says, with `DEBUG=true`, the value `.env.example` carries. The seed refuses to run without it.

## Steps

1. **Seed and start.** Run `scripts/seeded.sh start`, a plain foreground call. It stops any seeded server already running, then runs `manage.py seededserver` in the background, which rebuilds the database at `DATABASE_PATH` from nothing, the dev's local data included, and serves `http://127.0.0.1:8000/` without autoreload. The script returns once the server answers, printing the seeded voters, their password and the admin's password. Options pass through to `seededserver`: `--phase` picks the phase to seed, one of the five (#25, #74), and `/` then shows that phase's page. To pick up a code change or a fresh seed, run `start` again.
2. **Sign in once,** in one `browser_run_code_unsafe` call, with the passwords `start` printed. The browser keeps its cookies across calls, and one context holds a voter's session and the admin's together (#76), so leave out the half your states don't need:

   ```js
   async (page) => {
     page.setDefaultTimeout(5000);
     await page.goto('http://127.0.0.1:8000/login/');
     await page.fill('#id_username', 'Ada');
     await page.fill('#id_password', '<the voters’ password>');
     await Promise.all([page.waitForURL(url => !url.pathname.startsWith('/login/')), page.press('#id_password', 'Enter')]);
     await page.goto('http://127.0.0.1:8000/console/login/');
     await page.fill('#id_password', '<the admin’s password>');
     await Promise.all([page.waitForURL(url => !url.pathname.startsWith('/console/login/')), page.press('#id_password', 'Enter')]);
     return page.url();
   }
   ```

   Every cookie is `Secure`, so only the loopback address `127.0.0.1` keeps them (#31). The MCP holds one browser context, so a check needing two voters signed in at once needs a plain Playwright script (#25).
3. **Script each state.** A state is one thing the change shows: a page, an open card, a refusal, the region after a swap. Check each with one `browser_run_code_unsafe` call that reaches the state at both widths, screenshots it and returns what it measured. Each browser call re-reads your whole context, so a state walked one click at a time costs many times its script. Start from this shape:

   ```js
   async (page) => {
     page.setDefaultTimeout(5000);
     const out = {};
     for (const [width, height, name] of [[1280, 720, 'desktop'], [390, 844, '390']]) {
       await page.setViewportSize({ width, height });
       await page.goto('http://127.0.0.1:8000/…');
       // Reach the state: click, fill, drag, then wait for what the action swaps in.
       const region = page.locator('…');
       await region.screenshot({ path: `C:/Ribcage_main/tmp/<ticket>-<state>-${name}.png` });
       out[name] = {
         text: (await region.innerText()).slice(0, 400),
         overflows: await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
       };
     }
     return out;
   }
   ```

   - **Return the facts the state is judged on:** the text shown, a count, a computed style, a bounding box. A fact returned needs no second call to read.
   - **Frame each state.** Screenshot the element the change touches, through its locator, so it fills the frame. A shot of the page's top can leave a card lower down off-screen.
   - **Compare across an action.** Where an action swaps part of the page, as an htmx save, a refusal, or opening or closing a card does, screenshot the same element before and after in the one script. A control that moves, wraps or resizes across the swap is a finding.
   - **Give screenshots an absolute path under `tmp/`.** The function gets `page` alone, with no `require` and no file access of its own.
   - **A locator that misses fails in 5 s.** Take the selector from the template's source and rerun the script. Single calls such as `browser_snapshot` are for exploring a page whose source doesn't settle it.
4. **Read the screenshots,** a state's two in one message, for overflow, overlap, shifts and illegible text. Screenshots are evidence for this check alone, never baselines and never committed (#25). Done when every state the change touches has a screenshot at each width and you have read each one.
5. **Read the console.** After the last state, call `browser_console_messages` with level `error` and `all` set, and expect it empty. Read the server's log, `tmp/seededserver.log`, for tracebacks too.
6. **Stop the server, and leave the browser open.** The browser is in-memory (`--isolated`) and goes with the session; `browser_close` hangs, so leave it uncalled. Run `scripts/seeded.sh stop`, which kills the server's process tree and returns once it no longer answers. Done when it prints `Stopped.`
7. **Report** each state at each width: what the script did, the facts it returned, the console errors, and the screenshot filenames.
