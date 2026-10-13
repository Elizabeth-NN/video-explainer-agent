#!/usr/bin/env bash
set -euo pipefail

# Always run from the project root, regardless of where this script is called.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "======================================"
echo "   EXPLAINER VIDEO AGENT — GIT PUSH"
echo "======================================"

# Confirm this is a Git repository.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: This directory is not a Git repository."
    exit 1
fi

# Confirm an origin remote is configured.
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "ERROR: No Git remote named 'origin' is configured."
    echo "Add your GitHub repository with:"
    echo "  git remote add origin YOUR_GITHUB_REPOSITORY_URL"
    exit 1
fi

BRANCH="$(git branch --show-current)"

if [[ -z "$BRANCH" ]]; then
    echo "ERROR: You are not on a named Git branch."
    exit 1
fi

echo "Current branch: $BRANCH"

echo
echo "Current changes:"
git status --short
echo

read -r -p "Enter a commit message: " COMMIT_MESSAGE

if [[ -z "${COMMIT_MESSAGE// /}" ]]; then
    echo "ERROR: Commit message cannot be empty."
    exit 1
fi

git add -A

if git diff --cached --quiet; then
    echo "No staged changes to commit."
    exit 0
fi

echo
echo "Files staged for commit:"
git diff --cached --stat
echo

read -r -p "Commit these changes and push branch '$BRANCH'? [y/N] " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled. Your changes have not been committed by this script."
    exit 0
fi

git commit -m "$COMMIT_MESSAGE"
git push -u origin "$BRANCH"

echo
echo "Success! Your changes have been pushed to GitHub."
echo "Branch: $BRANCH"
