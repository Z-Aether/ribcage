# Runbook

The steps for running a window. Commands run from the repo root against the local stack, with `.env` copied from `.env.example`. On the host, the same `exec`, `cp`, `stop` and `start` go through whatever the Komodo account reaches, recorded on #54, and anything it can't reach is asked of Adam (#18).

## Backups

The stack's `backup` sidecar takes one backup at 04:00 in `TIME_ZONE` every night, onto the `backups` volume, and keeps the 7 newest (#30, #53).

- **Each backup** is SQLite's online backup of `/data/db.sqlite3`, so it holds the WAL's writes too. It passes `PRAGMA integrity_check` before it counts, and it is one file, `backup-<UTC date>-<UTC time>.sqlite3`, with no `-wal` beside it.
- **The sidecar's log** names the next backup's time, then each backup with its row counts, deletions and failures: `docker compose -f compose.yaml -f compose.local.yaml logs backup`. Nobody watches it, so a dead sidecar shows only here (#25).

### Take one now

```
docker compose -f compose.yaml -f compose.local.yaml exec backup python -m ribcage.operations.backup now
```

It prints `Took backup-…sqlite3:` and every table's row count, then deletes all but the 7 newest. To list them:

```
docker compose -f compose.yaml -f compose.local.yaml exec backup sh -c "ls -l /backups"
```

Git Bash rewrites an argument that starts with `/` into a Windows path, so a container path goes inside `sh -c "…"` or after `backup:` as above.

### Pull one into `private/`

A pulled backup goes only in `private/backups/`, never Downloads or a synced folder, so teardown deletes every local copy in one place (#30). Create the folder once, then copy the backup out of the sidecar and check that it opens, reading its row counts:

```
docker compose -f compose.yaml -f compose.local.yaml cp backup:/backups/<name> private/backups/
.venv/Scripts/python -m ribcage.operations.backup counts private/backups/<name>
```

## Restore

A backup restores into a fresh stack and is checked by row count. Restoring over a running stack's database is steps 2 to 5.

1. **Bring up a fresh stack.** `down -v` deletes both volumes, database and backups, so pull the backup first. The app migrates the new, empty database; `--wait` returns before that finishes, so wait until `http://127.0.0.1:8000/` answers.
   ```
   docker compose -f compose.yaml -f compose.local.yaml down -v
   docker compose -f compose.yaml -f compose.local.yaml up --build --detach --wait
   ```
2. **Stop the app**, so nothing writes while the database is replaced. The sidecar keeps running.
   ```
   docker compose -f compose.yaml -f compose.local.yaml stop ribcage
   ```
3. **Copy the backup onto the sidecar's volume.** It then counts as one of the 7.
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
6. **Check the row counts.** The live database's counts must match those of the pulled backup, apart from any migrations step 5 applied, then the app must serve its data at `http://127.0.0.1:8000/`.
   ```
   docker compose -f compose.yaml -f compose.local.yaml exec backup python -m ribcage.operations.backup counts
   ```
