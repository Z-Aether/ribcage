#!/usr/bin/env bash
# Builds, tests, pushes and pins a new image: the runbook's Rebuild steps 1 to 4, in one run (#59).
# Usage: scripts/release.sh "<what changed>" <ticket> [--skip-tests]
#   scripts/release.sh "the theme" 59   commits "Pin the stack to the theme (#59)"
set -euo pipefail

die() { echo "release: $*" >&2; exit 1; }

[ $# -ge 2 ] || die 'usage: scripts/release.sh "<what changed>" <ticket> [--skip-tests]'
WHAT=$1
TICKET=${2#\#}
SKIP_TESTS=${3:-}
[[ $TICKET =~ ^[0-9]+$ ]] || die "the ticket is a number, not '$2'"
[ -z "$SKIP_TESTS" ] || [ "$SKIP_TESTS" = --skip-tests ] || die "unknown option '$SKIP_TESTS'"

cd "$(git rev-parse --show-toplevel)"
PYTHON=.venv/Scripts/python
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

# The registry path is whatever the pin already carries, so it lives in compose.yaml alone.
REGISTRY=$(sed -n 's|^ *image: &pinned \([^ ]*\):[^:]*$|\1|p' compose.yaml | tr -d '\r')
[ -n "$REGISTRY" ] || die "no 'image: &pinned' line in compose.yaml"
REGISTRY_HOST=${REGISTRY%%/*}
REGISTRY_HOST=${REGISTRY_HOST%%:*}

echo "== Checking the tree"
[ -z "$(git status --porcelain)" ] || die "the tree isn't clean; commit or stash first"
[ "$(git branch --show-current)" = main ] || die "release from main"
git fetch --quiet origin main
git merge-base --is-ancestor HEAD origin/main || die "HEAD isn't on origin/main yet; push it first"

# On Adam's VPN the registry resolves to a LAN address and the push times out.
ADDRESS=$("$PYTHON" -c "import socket, sys; print(socket.gethostbyname(sys.argv[1]))" "$REGISTRY_HOST") \
  || die "can't resolve $REGISTRY_HOST"
if "$PYTHON" -c "import ipaddress, sys; sys.exit(not ipaddress.ip_address(sys.argv[1]).is_private)" "$ADDRESS"; then
  die "$REGISTRY_HOST resolves to $ADDRESS, a private address: disconnect from Adam's VPN"
fi

TAG=$(date -u +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)
echo "== Building ribcage:$TAG"
docker build --pull --platform linux/amd64 -t "ribcage:$TAG" .

if [ -z "$SKIP_TESTS" ]; then
  echo "== Running the tests"
  "$PYTHON" -m pytest -n 4
  "$PYTHON" -m pytest tests/image -m slow
fi

echo "== Pushing $REGISTRY:$TAG"
docker tag "ribcage:$TAG" "$REGISTRY:$TAG"
docker push "$REGISTRY:$TAG" || die "the push failed; if it asked for a login, run: docker login ${REGISTRY%%/*}"

echo "== Pinning compose.yaml"
# Only the tag's characters are replaced, so the line keeps its ending.
sed -b -i "s|^\( *image: &pinned [^ ]*:\)[0-9A-Za-z._-]*|\1$TAG|" compose.yaml
grep -q "image: &pinned $REGISTRY:$TAG" compose.yaml || die "compose.yaml wasn't re-pinned"
git commit --quiet -m "Pin the stack to $WHAT (#$TICKET)" -- compose.yaml
git log --oneline -1

# Only the image just pushed stays, and no build cache: older images are in the registry, and the rest rebuilds on demand.
echo "== Removing older images"
for image in $(docker images --format '{{.Repository}}:{{.Tag}}' ribcage) $(docker images --format '{{.Repository}}:{{.Tag}}' "$REGISTRY"); do
  case $image in
    "ribcage:$TAG" | "$REGISTRY:$TAG") ;;
    *) docker rmi "$image" >/dev/null && echo "removed $image" || echo "kept $image: a container still uses it" ;;
  esac
done
docker image prune --force >/dev/null
docker builder prune --all --force >/dev/null

cat <<EOF

Pushed $REGISTRY:$TAG and pinned compose.yaml to it.
Next: push the pin commit when you're ready, then carry on from the runbook's Rebuild step 2.
EOF
