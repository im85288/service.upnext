#!/bin/bash
# Keep the Kodi repo-scripts submission tidy around the submitter action:
#   close-superseded <tag>  close our open service.upnext PRs for older versions, so the submitter
#                           opens a new PR instead of pushing this version into one with an old title
#   verify <tag>            check that the submitted branch carries this version and that its PR is open
# Needs GH_TOKEN and GH_USERNAME (the account the submitter pushes from). DRY_RUN=1 only prints.
set -euo pipefail

REPO=xbmc/repo-scripts
TITLE_PREFIX='[service.upnext@matrix]'
BRANCH='service.upnext@matrix'

action=${1:?usage: $0 close-superseded|verify <tag>}
tag=${2:?usage: $0 close-superseded|verify <tag>}
version=${tag#v}

open_prs() {
    gh pr list --repo "$REPO" --author "$GH_USERNAME" --state open --json number,title \
        --jq ".[] | select(.title | startswith(\"$TITLE_PREFIX \")) | \"\(.number) \(.title)\""
}

case "$action" in
    close-superseded)
        open_prs | while read -r number title; do
            if [ "$title" = "$TITLE_PREFIX $version" ]; then
                echo "Keeping #$number, it is already for $version"
                continue
            fi
            echo "Closing #$number ($title), superseded by $version"
            if [ "${DRY_RUN:-}" != 1 ]; then
                gh pr close "$number" --repo "$REPO" --comment "Superseded by $version"
            fi
        done
        ;;
    verify)
        # The submitter hides git errors, and once left the branch on an older version while still opening a PR
        for attempt in 1 2 3; do
            # A temporary GitHub error counts as a mismatch, so it gets the same retries
            submitted=$(gh api "repos/$GH_USERNAME/repo-scripts/contents/service.upnext/addon.xml?ref=$BRANCH" --jq .content \
                | base64 -d | sed -n 's/^<addon id="service.upnext" name="Up Next" version="\([^"]*\)".*/\1/p') || submitted=
            pr=$(open_prs | awk -v t="$TITLE_PREFIX $version" 'substr($0, index($0, " ") + 1) == t {print $1}') || pr=
            echo "Submitted addon.xml version: ${submitted:-none}, open PR for $version: ${pr:-none}"
            if [ "$submitted" = "$version" ] && [ -n "$pr" ]; then
                echo "Kodi submission OK: https://github.com/$REPO/pull/$pr"
                exit 0
            fi
            [ "$attempt" = 3 ] || sleep 20
        done
        echo "::error::The Kodi submission does not match $tag; check $GH_USERNAME/repo-scripts@$BRANCH and the PRs on $REPO"
        exit 1
        ;;
    *)
        echo "Unknown action: $action" >&2
        exit 2
        ;;
esac
