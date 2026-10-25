#!/usr/bin/env bash
# Starts or stops the seeded instance for a browser check, in one call each (docs/agents/browser-verification.md).
# Usage: scripts/seeded.sh start [seededserver options, such as --phase VOTE]   reseeds, serves, prints the voters
#        scripts/seeded.sh stop
set -euo pipefail

die() { echo "seeded: $*" >&2; exit 1; }

cd "$(git rev-parse --show-toplevel)"
PYTHON=.venv/Scripts/python
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python
URL=http://127.0.0.1:8000/login/
LOG=tmp/seededserver.log

answers() { [ "$(curl -s -o /dev/null -w '%{http_code}' "$URL")" = 200 ]; }

stop() {
  if command -v taskkill >/dev/null; then
    # The venv's python.exe is a launcher whose child interpreter serves, so kill both trees.
    local pids
    pids=$(powershell -NoProfile -Command '
      @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "*\.venv\*" -and $_.CommandLine -like "*manage.py seededserver*" } | ForEach-Object ProcessId) +
      @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object OwningProcess)' | tr -d '\r')
    for pid in $pids; do taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true; done
  else
    pkill -f 'manage.py seededserver' || true
  fi
  for _ in $(seq 1 20); do answers || return 0; sleep 0.5; done
  die "still answering on 127.0.0.1:8000 after the kill"
}

case ${1:-} in
  start)
    shift
    stop
    mkdir -p tmp
    PYTHONUNBUFFERED=1 nohup "$PYTHON" manage.py seededserver "$@" > "$LOG" 2>&1 < /dev/null &
    server=$!
    disown
    for _ in $(seq 1 120); do
      answers && break
      # A refused option or a failed seed exits at once, so stop waiting and show why.
      kill -0 "$server" 2>/dev/null || { cat "$LOG" >&2; die "seededserver exited before serving; its log is above"; }
      sleep 0.5
    done
    answers || { tail -20 "$LOG" >&2; die "not answering after 60 s; the log is above"; }
    grep -v '"GET ' "$LOG"
    echo "Serving http://127.0.0.1:8000/; the server's log is $LOG."
    ;;
  stop)
    stop
    echo "Stopped."
    ;;
  *) die "usage: scripts/seeded.sh start [--phase PHASE] | stop" ;;
esac
