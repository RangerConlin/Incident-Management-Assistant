#!/usr/bin/env bash
set -euo pipefail

# Usage: run from the repository root:
#   chmod +x scripts/force_main_from_branch.sh
#   scripts/force_main_from_branch.sh
#
# This script will:
# - fetch the remote
# - fail if working tree is dirty
# - create a timestamped backup branch from origin/main and push it
# - reset local `main` to `incident-organization-rewrite`
# - force-push `main` to the remote

BRANCH="incident-organization-rewrite"
REMOTE="origin"
BACKUP_BRANCH="backup/main-before-reset-$(date +%Y%m%d%H%M%S)"

if [ ! -d .git ]; then
  echo "ERROR: .git not found. Run this from the repository root." >&2
  exit 1
fi

echo "Fetching $REMOTE..."
git fetch "$REMOTE" --prune

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: Working tree is not clean. Commit or stash changes first." >&2
  git status --porcelain
  exit 1
fi

if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  echo "Branch '$BRANCH' not found locally; attempting to fetch from $REMOTE..."
  if git ls-remote --exit-code "$REMOTE" "refs/heads/$BRANCH" >/dev/null 2>&1; then
    git fetch "$REMOTE" "$BRANCH":"$BRANCH"
  else
    echo "ERROR: Branch '$BRANCH' not found on remote $REMOTE." >&2
    exit 1
  fi
fi

if git ls-remote --exit-code "$REMOTE" refs/heads/main >/dev/null 2>&1; then
  echo "Creating backup branch '$BACKUP_BRANCH' from $REMOTE/main locally and pushing it..."
  git branch -f "$BACKUP_BRANCH" "$REMOTE/main"
  git push "$REMOTE" "$BACKUP_BRANCH":"$BACKUP_BRANCH"
else
  echo "No remote main branch found at $REMOTE/main; skipping backup push."
fi

echo "Resetting local 'main' to '$BRANCH' and force-pushing to $REMOTE/main"
git checkout -B main "$BRANCH"
git push "$REMOTE" main --force

echo "Local 'main' now matches '$BRANCH' and remote '$REMOTE/main' was force-pushed."
echo "A backup branch was created: $BACKUP_BRANCH (pushed to $REMOTE)."

echo "Switching back to '$BRANCH'"
git checkout "$BRANCH"

echo "Done."
