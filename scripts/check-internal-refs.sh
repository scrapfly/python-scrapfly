#!/usr/bin/env bash
# Refuse to publish internal-only references.
#
# This repository is public. Everything tracked here is readable by customers,
# competitors and crawlers, comments included. The patterns below are things
# that only exist inside the private monorepo: source layout, dev hostnames,
# ticket ids, agent scratch paths. A comment may explain WHAT the API does; it
# may not say WHERE our server code lives.
#
# Usage:  scripts/check-internal-refs.sh [--staged]
#   (no args)  scan every tracked file   — what CI runs
#   --staged   scan the index instead     — what a pre-commit hook runs
#
# An accepted exception goes in .internal-refs-allow, one extended regex per
# line, matched against "path:line:text". Comments and blank lines ignored.

set -uo pipefail

mode="${1:-all}"
allow_file=".internal-refs-allow"

# One pattern per class. Kept separate rather than alternated into a single
# regex so a hit names the class it violated.
patterns=(
  'apps/scrapfly/'                        # monorepo application paths
  'scrapfly-apps'                         # the private monorepo itself
  'scrapfly-api/pkg'                      # api internals
  'web-app/src/'                          # dashboard internals
  'scrape_engine/'                        # scrape engine internals
  '[a-z0-9-]+\.(scrapfly|web-scraping-dev)[a-z0-9.-]*\.?(home|local)\b'  # internal dev hostnames
  '(scrapfly|web-scraping-dev)[a-z0-9.-]*\.(home|local)\b'
  '/root/'                                # agent and developer machine paths
  '/home/[a-z]'
  '/opt/(go-sdk|mcp-oss)'                 # container-only replace targets
  '\.claude/projects/'                    # agent session and memory paths
  'TIC-[0-9A-Fa-f]{4}-[0-9]'              # support ticket ids
  '(SCRAPE-ENGINE|CLOUD-BROWSER|SCRAPIUM|WEB-APP|API)-[0-9][0-9A-Z]*'  # sentry issue ids
  'production-[0-9]{6}'                   # gcp project id
  'scrapfly-staff'                        # internal staff cli
)

if [ "$mode" = "--staged" ]; then
  search() { git grep -nIE --cached "$1" 2>/dev/null; }
else
  search() { git grep -nIE "$1" 2>/dev/null; }
fi

# The allowlist is read once into a regex file; an empty one matches nothing.
allow_rules=$(mktemp)
trap 'rm -f "$allow_rules"' EXIT
[ -f "$allow_file" ] && grep -vE '^[[:space:]]*(#|$)' "$allow_file" > "$allow_rules"

allowed() {
  [ -s "$allow_rules" ] || return 1
  printf '%s' "$1" | grep -qE -f "$allow_rules"
}

hits=0
for pattern in "${patterns[@]}"; do
  while IFS= read -r hit; do
    [ -z "$hit" ] && continue
    case "$hit" in
      "$allow_file":*) continue ;;               # the allowlist quotes patterns by design
      scripts/check-internal-refs.sh:*) continue ;;  # so does this script
    esac
    allowed "$hit" && continue
    printf 'internal reference [%s]\n  %s\n' "$pattern" "$hit"
    hits=$((hits + 1))
  done <<< "$(search "$pattern")"
done

if [ "$hits" -gt 0 ]; then
  cat >&2 <<MSG

$hits internal reference(s) would be published by this commit.

Rewrite the line to describe the observable API behaviour instead of our
internal location, or add a justified exception to $allow_file.
MSG
  exit 1
fi
