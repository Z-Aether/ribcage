# Runbook

The steps for running a window: the rebuild at its start, backups and restores during it, and the teardown at its end (#18, #30).

- **Local commands** run in Git Bash from the repo root. Those against the local stack expect `.env` copied from `.env.example`.
- **Host steps** go through the dev's Komodo account (v2.3.3). It reaches each service's logs, stop, start and restart, the stack's *Deploy* and *Destroy*, a *Terminal* in either container, and the server's volumes. It can't download or upload a file. Anything it can't do is asked of Adam (#18, #54).
- **`<subdomain>`** stands for the live address, the bare name in `ALLOWED_HOSTS`.

## Rebuild

At the start of each window. Teardown left the stack definition and its environment on Komodo and removed both volumes, so this deploys an empty app. A redeploy mid-window follows the same steps; take a backup first and copy its row counts into a note, because *Deploy* replaces the containers and closes their terminals (#59). The `counts` check afterwards compares against them.

1. **Release the image, off Adam's VPN,** from a clean tree at a commit already pushed to `main`. Each build pulls the patched base image, which is why every window rebuilds (#18, #59).
   ```
   scripts/release.sh "<what changed>" <n>
   ```
   It stops at the first failure, naming it. In order, it:
   - **refuses while the registry resolves to a private address.** On the VPN it resolves to a LAN address and the push times out.
   - **builds** `ribcage:<UTC minute>-<commit>`.
   - **runs every suite.** `tests/image` builds its own `ribcage:pytest` from the same clean tree, so it checks this build's Dockerfile and stack.
   - **pushes** it to the registry path the pin carries. If the push asks for a login, run `docker login registry.brabulla.xyz:5050`, then rerun with `--skip-tests` after the suites.
   - **re-pins** the `image: &pinned` line, which the `backup` sidecar follows through the anchor, and commits it as `Pin the stack to <what changed> (#n)`. Push that commit before the next release, which needs it on `origin/main`.
   - **removes** every other local `ribcage` image and the build cache: older images stay in the registry.
2. **Set the stack's environment in Komodo,** with your copy in `private/komodo-stack.env`.
   - **Values are URL-safe text,** with no `$`, `#`, quotes or spaces. Komodo's `.env` handling cuts a value at `$` and treats ` #` as a comment. Generate each secret with `.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(50))"`.
   - **New for each window:** `SECRET_KEY`, `JOIN_CODE` and `ADMIN_PASSWORD`. The last window's join code went round the group chat.
   - **Carried over:** `TMDB_API_KEY` and `DTDD_API_KEY` from `private/credentials/`, and `TIME_ZONE` (`Europe/Budapest`).
   - **The address:** `ALLOWED_HOSTS` is `<subdomain>`, and `CSRF_TRUSTED_ORIGINS` is `https://<subdomain>`.
   - **Tuning constants** stay empty, which keeps each one's default. Changing one later is an environment edit and a redeploy, with no rebuild (#25).
   - **Auto-update stays off.** In the stack's settings, *Poll for Updates* and *Auto Update* are both off (#40).
3. **Paste `compose.yaml` into the stack's compose editor, then *Deploy*.** Komodo lists both services, `ribcage` and `backup`, on the new tag.
4. **Check it.** A missing required variable stops startup with `Set the <NAME> environment variable.` in `ribcage`'s log, and the container restarts in a loop.
   - **From outside the host's network,** a phone on mobile data for instance, `https://<subdomain>/` loads with a valid certificate. `curl -I http://<subdomain>/` returns `301` to `https://`.
   - **HSTS:** the host's proxy removes it from responses (#54), so check it in the `ribcage` container's *Terminal*. It prints `200 max-age=31536000; includeSubDomains`.
     ```
     python -c "import http.client as h; c = h.HTTPConnection('127.0.0.1', 8000); c.request('HEAD', '/login/', headers={'Host': '<subdomain>'}); r = c.getresponse(); print(r.status, r.getheader('Strict-Transport-Security'))"
     ```
   - **A form POST** through `https://<subdomain>/login/` gets past CSRF: logging in with any name and password answers *The display name or the password is wrong.* A `403` means `CSRF_TRUSTED_ORIGINS` doesn't match the address in the browser.
   - **The `backup` log** says `Next backup at … 04:00 Europe/Budapest.`

### Roll back

Rolling back is putting the previous tag back on the pin and deploying, but only while no migration lies between the two images. The app migrates at start, so older code would meet a newer schema. Check with the two commits, the last part of each tag:

```
git diff --name-only <old commit> <new commit> -- "ribcage/*/migrations/*"
```

If that lists anything, roll back by restoring a backup taken before the upgrade instead.

## Backups

The stack's `backup` sidecar takes one backup at 04:00 in `TIME_ZONE` every night, onto the `backups` volume, and keeps the 7 newest (#30, #53).

- **Each backup** is SQLite's online backup of `/data/db.sqlite3`, so it holds the WAL's writes too. It passes `PRAGMA integrity_check` before it counts, and it is one file, `backup-<UTC date>-<UTC time>.sqlite3`, with no `-wal` beside it.
- **The sidecar's log** names the next backup's time, then each backup with its row counts, deletions and failures: `docker compose -f compose.yaml -f compose.local.yaml logs backup`, or the `backup` service's log in Komodo. Nobody watches it, so a dead sidecar shows only here (#25).
- **A night missed while the sidecar is down is not made up.** After a redeploy or an outage that spanned 04:00, take one now.

### Take one now

```
docker compose -f compose.yaml -f compose.local.yaml exec backup python -m ribcage.operations.backup now
```

It prints `Took backup-…sqlite3:` and every table's row count, then deletes all but the 7 newest. To list them:

```
docker compose -f compose.yaml -f compose.local.yaml exec backup sh -c "ls -l /backups"
```

On the host, run the same `python -m ribcage.operations.backup now` and `ls -l /backups` in the `backup` container's *Terminal*.

Git Bash rewrites an argument that starts with `/` into a Windows path, so a container path goes inside `sh -c "…"` or after `backup:` as above.

### Pull one into `private/`

A pulled backup goes only in `private/backups/`, never Downloads or a synced folder, so teardown deletes every local copy in one place (#30). Copy the backup out of the sidecar and check that it opens, reading its row counts:

```
mkdir -p private/backups
docker compose -f compose.yaml -f compose.local.yaml cp backup:/backups/<name> private/backups/
.venv/Scripts/python -m ribcage.operations.backup counts private/backups/<name>
```

### Pull one from the host

Komodo can't download a file, so for now a backup leaves the host as text, copied out of the `backup` container's *Terminal* (#54). M3 replaces this with a download on the admin side (#68).

1. **In the terminal, note the backup's checksum and its length in lines.** Take one with `python -m ribcage.operations.backup now`, or pick one from `ls -l /backups`.
   ```
   sha256sum /backups/<name>
   gzip -nc /backups/<name> | base64 | wc -l
   ```
2. **Print it in parts of 1000 lines,** and paste each part, in order, into one new file, `private/backups/<name>.b64`. `-n` makes gzip give the same output on every run, so the parts join up. Keep going until you reach step 1's line count. If the top of a part has scrolled out of the terminal, print smaller parts.
   ```
   gzip -nc /backups/<name> | base64 | sed -n "1,1000p"
   gzip -nc /backups/<name> | base64 | sed -n "1001,2000p"
   ```
3. **Decode it in Git Bash** and check that the checksum matches step 1's:
   ```
   base64 -d private/backups/<name>.b64 | gunzip > private/backups/<name>
   sha256sum private/backups/<name>
   ```
4. **Delete the `.b64` file,** then check that the backup opens, reading its row counts. They match the counts the host printed when it took the backup, in `now`'s output or the sidecar's log.
   ```
   rm private/backups/<name>.b64
   .venv/Scripts/python -m ribcage.operations.backup counts private/backups/<name>
   ```

## Restore

A backup restores into a fresh stack and is checked by row count. Restoring over a running stack's database is steps 2 to 6.

1. **Bring up a fresh stack.** `down -v` deletes both volumes, database and backups, so pull the backup first. The app migrates the new, empty database. There is no healthcheck, so `--wait` returns before that finishes: wait until `http://127.0.0.1:8000/` answers.
   ```
   docker compose -f compose.yaml -f compose.local.yaml down -v
   docker compose -f compose.yaml -f compose.local.yaml up --build --detach --wait
   ```
2. **Stop the app**, so nothing writes while the database is replaced. The sidecar keeps running.
   ```
   docker compose -f compose.yaml -f compose.local.yaml stop ribcage
   ```
3. **Copy the backup onto the sidecar's volume.** It then counts as one of the 7, sorted by the time in its name, so an old one copied beside 7 newer ones is deleted at the next backup.
   ```
   docker compose -f compose.yaml -f compose.local.yaml cp private/backups/<name> backup:/backups/
   ```
4. **Restore it.** The sidecar checks its integrity, then writes it over the database through SQLite rather than as a file copy, so a stale `-wal` beside the database is never replayed onto it. It prints the restored row counts.
   ```
   docker compose -f compose.yaml -f compose.local.yaml exec backup python -m ribcage.operations.backup restore <name>
   ```
5. **Start the app.** Its startup migrates a backup from an older schema forward.
   ```
   docker compose -f compose.yaml -f compose.local.yaml start ribcage
   ```
6. **Check the row counts.** The live database's counts must match those of the pulled backup, apart from any migrations step 5 applied, then logging in at `http://127.0.0.1:8000/login/` as a voter from the backup must reach `/`.
   ```
   docker compose -f compose.yaml -f compose.local.yaml exec backup python -m ribcage.operations.backup counts
   ```

### On the host, from its own volume

When the database is damaged but the `backups` volume holds a good backup, the same steps run in Komodo, with nothing to copy.

1. **Stop the `ribcage` service,** leaving `backup` running.
2. **In the `backup` container's *Terminal*,** pick a backup from `ls -l /backups`, then restore it:
   ```
   python -m ribcage.operations.backup restore <name>
   ```
3. **Start the `ribcage` service,** then run `python -m ribcage.operations.backup counts` in the same terminal and compare with the counts `restore` printed.

### On the host, from a pulled copy

When the host's volumes are lost, the pulled copy goes back in the way it came out, pasted into the `backup` container's *Terminal* as text. **Not yet run on the host:** the pipeline is checked against the deployed image locally, but not yet through Komodo's terminal (#55). M3's download page is to carry a backup back in by the same one-time code (#68).

1. **Bring up a fresh stack:** *Destroy* the stack, delete both volumes as in Teardown, then *Deploy*. Wait until `https://<subdomain>/` answers, then stop the `ribcage` service.
2. **In Git Bash, note the backup's checksum and its length in lines.**
   ```
   sha256sum private/backups/<name>
   gzip -nc private/backups/<name> | base64 | wc -l
   ```
3. **Paste it in parts of 1000 lines.** Copy a part to the clipboard in Git Bash:
   ```
   gzip -nc private/backups/<name> | base64 | sed -n "1,1000p" | clip
   ```
   Then, in the `backup` container's terminal, type the first line below, paste the part, and type `END` on a line of its own. Repeat with `"1001,2000p"` and so on, until you reach step 2's line count. If a paste comes through incomplete, use smaller parts.
   ```
   cat >> /backups/<name>.b64 <<'END'
   END
   ```
4. **Decode it in the terminal.** The line count and the checksum must match step 2's. Then delete the `.b64` file.
   ```
   wc -l < /backups/<name>.b64
   base64 -d /backups/<name>.b64 | gunzip > /backups/<name>
   sha256sum /backups/<name>
   rm /backups/<name>.b64
   ```
5. **Restore, start and check** as steps 2 and 3 of *On the host, from its own volume*. The counts match those `counts` printed for the pulled copy.

## Teardown

At the end of every window, the morning after the evening, and also when a marathon is abandoned. The data is deleted, not kept. The one exception is the pseudonymised score matrix taken at the reveal, kept outside the repo and outside `private/` (#25, #30).

1. **Stop the `ribcage` service, then *Destroy* the stack in Komodo.** That removes both containers and their logs, and keeps the stack definition and its environment for the next rebuild. *Destroy* keeps the named volumes (#54).
2. **Delete both volumes** on the server's page in Komodo: the two whose names end in `_data` and `_backups`. Docker won't delete a volume a container still uses, which is why *Destroy* comes first.
   - **If the account can't delete volumes** (Adam may narrow it), empty them before step 1's *Destroy*, then ask Adam to remove the two empty volumes. With `ribcage` stopped, run this in the `backup` container's *Terminal*:
     ```
     rm -f /data/db.sqlite3* /backups/*
     ```
3. **Check that nothing of ours answers:** `https://<subdomain>/` returns the proxy's bare 502.
4. **Delete every local copy.** Pulled backups are in `private/backups/`. A local stack a real backup was restored into goes with `down -v`.
   ```
   rm -rf private/backups
   docker compose -f compose.yaml -f compose.local.yaml down -v
   ```
   `private/credentials/`, `private/komodo-stack.env` and `private/past-marathons/` stay: they hold none of the app's data.
