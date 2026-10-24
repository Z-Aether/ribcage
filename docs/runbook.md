# Runbook

The steps for running a window: the rebuild at its start, backups and restores during it, and the teardown at its end (#18, #30).

- **Local commands** run in Git Bash from the repo root. Those against the local stack expect `.env` copied from `.env.example`.
- **Host steps** go through the dev's Komodo account (v2.3.3). It reaches each service's logs, stop, start and restart, the stack's *Deploy* and *Destroy*, a *Terminal* in either container, and the server's volumes. It can't download or upload a file. Anything it can't do is asked of Adam (#18, #54).
- **`<subdomain>`** stands for the live address, the full host name in `ALLOWED_HOSTS`, without `https://`. The first label alone is not it: the app answers it `400`.

## Rebuild

At the start of each window. Teardown left the stack definition and its environment on Komodo and removed both volumes, so this deploys an empty app. A redeploy mid-window follows the same steps; take a backup first and copy its row counts into a note, because *Deploy* replaces the containers and closes their terminals (#59). The `counts` check afterwards compares against them.

1. **Release the image, off Adam's VPN,** from a clean tree at a commit already pushed to `main`. Each build pulls the patched base image, which is why every window rebuilds (#18, #59).
   ```
   scripts/release.sh "<what changed>" <n>
   ```
   It stops at the first failure, naming it, so run it in a Git Bash window that's already open: started from PowerShell or Explorer, it opens a window of its own, which closes at the failure before you can read it (#82). In order, it:
   - **refuses while the registry resolves to a private address.** On the VPN it resolves to a LAN address and the push times out.
   - **builds** `ribcage:<UTC minute>-<commit>`.
   - **runs every suite.** `tests/image` builds its own `ribcage:pytest` from the same clean tree, so it checks this build's Dockerfile and stack.
   - **pushes** it to the registry path the pin carries. If the push asks for a login, run `docker login registry.brabulla.xyz:5050`, then rerun with `--skip-tests` after the suites.
   - **re-pins** the `image: &pinned` line, which the `backup` sidecar follows through the anchor, and commits it as `Pin the stack to <what changed> (#n)`. Push that commit before the next release, which needs it on `origin/main`.
   - **removes** every other local `ribcage` image and the build cache: older images stay in the registry.
2. **Set the stack's environment in Komodo,** with your copy in `private/komodo-stack.env`.
   - **Values are URL-safe text,** with no `$`, `#`, quotes or spaces. Komodo's `.env` handling cuts a value at `$` and treats ` #` as a comment. Generate each secret with `.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(50))"`.
   - **New for each window:** `SECRET_KEY`, `JOIN_CODE` and `ADMIN_PASSWORD`. The last window's join code went round the group chat.
   - **Carried over:** `TMDB_API_KEY` and `DTDD_API_KEY` from `private/credentials/`, `TIME_ZONE` (`Europe/Budapest`), and `ABUSE_EMAIL`, the address the footer's abuse link mails (#73).
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
   - **TMDB:** the app's search and film details call TMDB from the host, so check the stack's key reaches it, in the same *Terminal*. It prints `200 application/json;charset=utf-8`, and never the key. `HTTP 401` means `TMDB_API_KEY` is wrong; `FAILED` means the host's network blocks the call, which is a question for Adam (#100).
     ```
     python - <<'EOF'
     import os, urllib.request, urllib.error
     key = os.environ["TMDB_API_KEY"]
     url, headers = "https://api.themoviedb.org/3/configuration", {"accept": "application/json"}
     if key.count(".") == 2:
         headers["Authorization"] = "Bearer " + key
     else:
         url += "?api_key=" + key
     try:
         r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15)
         print(r.status, r.headers["Content-Type"])
     except urllib.error.HTTPError as e:
         print("HTTP", e.code)
     except Exception as e:
         print("FAILED", type(e).__name__)
     EOF
     ```
   - **DoesTheDogDie:** the app's content warnings call DoesTheDogDie from the host, so check the stack's key reaches it, in the same *Terminal*. It prints `200 application/json; charset=utf-8`, the item count and the requests left this minute, and never the key. `HTTP 401` or `403` means `DTDD_API_KEY` is wrong; `FAILED` means the host's network blocks the call, which is a question for Adam (#115).
     ```
     python - <<'EOF'
     import os, json, urllib.request, urllib.error
     key = os.environ.get("DTDD_API_KEY", "")
     if not key:
         raise SystemExit("DTDD_API_KEY is not set")
     url = "https://www.doesthedogdie.com/api/v3/topicsupercategories"
     headers = {"accept": "application/json", "X-API-KEY": key}
     try:
         r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15)
         body = json.load(r)
         items = body if isinstance(body, list) else next((v for v in body.values() if isinstance(v, list)), [])
         print(r.status, r.headers["Content-Type"], len(items), "items, remaining this minute:", r.headers["x-ratelimit-remaining-minute"])
     except urllib.error.HTTPError as e:
         print("HTTP", e.code)
     except Exception as e:
         print("FAILED", type(e).__name__)
     EOF
     ```
   - **A form POST** through `https://<subdomain>/login/` gets past CSRF: logging in with any name and password answers *The display name or the password is wrong.* A `403` means `CSRF_TRUSTED_ORIGINS` doesn't match the address in the browser. A silent return to the empty login form means the CSRF cookie never came back (#76).
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

Komodo can't download a file, so the admin side serves one, but only for a one-time code made in the `ribcage` container's *Terminal*. The admin password alone never yields the database (#54, #68). The code works once, for 10 minutes, and a wrong code voids it.

1. **Make a code.** In Komodo, open a *Terminal* in the `ribcage` container, not `backup`: only `ribcage` has the settings the command reads. Run:
   ```
   python manage.py backupcode download
   ```
   It takes a fresh backup, not one of the sidecar's, so its counts differ from an earlier backup's by whatever was written in between, such as a login's `django_session` row (#82). It checks the backup's integrity and prints three lines:
   - `Offered backup-<UTC date>-<UTC time>.sqlite3:` and every table's row count. Copy the counts into a note for step 4.
   - `Code:` and 32 letters and digits. Copy them.
   - the page's path, `/console/backup/`, and the time the code expires.

   Running it again, for either purpose, replaces the offer: the earlier code is then wrong, and entering it voids the new one too.
   - **Komodo's terminal opens as the image's user,** `ribcage` (#82). If one ever opens as root, the command says to run it as the image's user: run `su ribcage -s /bin/sh -c 'python manage.py backupcode download'` instead.
2. **Open `https://<subdomain>/console/backup/`** and log in as the admin if it asks. The console's Backup tab links to it (#86).
3. **Paste the code and press *Download*.** Save the file into `private/backups/`, never Downloads or a synced folder (#30). If the browser saves it without asking, move it from Downloads into `private/backups/` straight away.
   - **If the page says the code is wrong or expired,** the offer is void: go back to step 1 for a new code.
   - **If it says no backup is on offer,** the code was used already, or a wrong or expired code voided it: go back to step 1.
4. **Check that it opens, reading its row counts.** They match the counts you noted in step 1.
   ```
   .venv/Scripts/python -m ribcage.operations.backup counts private/backups/<name>
   ```

Nothing is left to clean up on the host. The offered file is deleted once it is downloaded, and an unused one once it has expired and the page or the command next runs. Teardown's wipe of the data volume removes anything else.

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

### On the host, from a pulled backup

When the host's volumes are lost, the pulled backup goes back in through the admin side, for a one-time code made in the `ribcage` container's *Terminal*: the pull's route in reverse (#81). The page only checks the file and keeps it on the data volume, `/data`, beside the database. The restore stays a step in the `backup` container's *Terminal*, which mounts `/data` too. The code works once, for 10 minutes, and a wrong code voids it.

1. **Bring up a fresh stack:** *Destroy* the stack, delete both volumes as in Teardown, then *Deploy*. Wait until `https://<subdomain>/` answers. Leave `ribcage` running: it serves the page.
2. **In Git Bash, note the pulled backup's row counts** for step 7:
   ```
   .venv/Scripts/python -m ribcage.operations.backup counts private/backups/<name>
   ```
3. **Make a code.** In Komodo, open a *Terminal* in the `ribcage` container, not `backup`, and run:
   ```
   python manage.py backupcode upload
   ```
   It prints `Code:` and 32 letters and digits, then the page's path and the time the code expires. Copy the code. Running the command again, for either purpose, replaces it.
   - **Komodo's terminal opens as the image's user,** `ribcage` (#82). If one ever opens as root, the command says to run it as the image's user: run `su ribcage -s /bin/sh -c 'python manage.py backupcode upload'` instead.
4. **Open `https://<subdomain>/console/backup/`** and log in as the admin if it asks. The console's Backup tab links to it (#86). Under *Upload a backup*, paste the code, choose `private/backups/<name>`, and press *Upload*.
   - **The page answers** `Kept backup-<UTC date>-<UTC time>.sqlite3:` and the file's row counts, which match step 2's, then the restore command for step 6. The kept name is the time of the upload, not the pulled backup's name: copy it. If you lose it, `ls /data` in the `backup` container's *Terminal* shows it; reloading the page only resubmits the used code.
   - **If it says the file is over 25 MB, is not an SQLite database, or failed the integrity check,** nothing was kept and the code wasn't tried: choose the right file and press *Upload* again with the same code. The cap is several times a marathon's database, which is a few MB, so a file over it is the wrong file; it stays low enough to arrive within the app server's 30-second limit at 10 Mbit/s even if the proxy passes the upload on unbuffered. The host's proxy passed a 5 MB upload (#82).
   - **If it says the code is wrong, expired or made for a download, or that no code is on offer,** nothing was kept and the code is void: go back to step 3.
5. **Stop the `ribcage` service,** leaving `backup` running, so nothing writes while the database is replaced.
6. **Restore it** in the `backup` container's *Terminal*, with the kept name from step 4. `--backups /data` makes the sidecar read it from the data volume instead of its own. It checks the file's integrity again, writes it over the database through SQLite, and prints the restored row counts.
   ```
   python -m ribcage.operations.backup restore <kept name> --backups /data
   ```
7. **Start the `ribcage` service, then check the row counts** in the same terminal. They match step 2's, apart from any migrations the start applied. Then logging in at `https://<subdomain>/login/` as a voter from the backup must reach `/`.
   ```
   python -m ribcage.operations.backup counts
   ```
8. **Delete the uploaded file** in the same terminal. It holds the whole database, so it doesn't wait for teardown. Afterwards `ls` lists only `backup-offer`, `db.sqlite3`, `db.sqlite3-shm` and `db.sqlite3-wal`. The `*` also takes the `-wal` and `-shm` files that restoring a WAL-mode upload leaves.
   ```
   rm /data/<kept name>*
   ls /data
   ```

## Teardown

At the end of every window, the morning after the evening, and also when a marathon is abandoned. The data is deleted, not kept. The one exception is the pseudonymised score matrix taken at the reveal, kept outside the repo and outside `private/` (#25, #30).

1. **Stop the `ribcage` service, then *Destroy* the stack in Komodo.** That removes both containers and their logs, and keeps the stack definition and its environment for the next rebuild. *Destroy* keeps the named volumes (#54).
2. **Delete both volumes** on the server's page in Komodo: the two whose names end in `_data` and `_backups`. Docker won't delete a volume a container still uses, which is why *Destroy* comes first.
   - **If the account can't delete volumes** (Adam may narrow it), empty them before step 1's *Destroy*, then ask Adam to remove the two empty volumes. With `ribcage` stopped, run this in the `backup` container's *Terminal*:
     ```
     rm -rf /data/db.sqlite3* /data/backup-* /backups/*
     ```
3. **Check that nothing of ours answers:** `https://<subdomain>/` returns the proxy's bare 502.
4. **Delete every local copy.** Pulled backups are in `private/backups/`. A local stack a real backup was restored into goes with `down -v`.
   ```
   rm -rf private/backups
   docker compose -f compose.yaml -f compose.local.yaml down -v
   ```
   `private/credentials/`, `private/komodo-stack.env` and `private/past-marathons/` stay: they hold none of the app's data.
