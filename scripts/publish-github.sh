#!/usr/bin/env bash
# Run ON YOUR OWN Linux system with `gh` authenticated. No tokens stored in repository.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/privacy_audit.py
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
command -v gh >/dev/null || { echo 'Install GitHub CLI: sudo apt install gh' >&2; exit 1; }
gh auth status >/dev/null || { echo 'Run: gh auth login' >&2; exit 1; }
REPO="${1:-tenettech-dev/BTLink.deb}"
case "$REPO" in */*) ;; *) echo 'Usage: publish-github.sh owner/repo' >&2; exit 1;; esac
if [[ ! -d .git ]]; then git init -b main; fi
if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add .
  git -c user.name='BTLink Community Contributors' \
      -c user.email='noreply@github.com' \
      commit -m 'Initial public Linux Wine BTLink package'
fi
if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "Repository already exists: $REPO"
  if ! git remote get-url origin >/dev/null 2>&1; then git remote add origin "https://github.com/$REPO.git"; fi
  git push -u origin main
else
  gh repo create "$REPO" --public --source . --remote origin --push \
    --description 'Unofficial open-source Linux Wine bridge and Debian package for KONNWEI BTLink'
fi
printf 'Public repository: https://github.com/%s\n' "$REPO"
VISIBILITY="$(gh repo view "$REPO" --json visibility --jq .visibility)"
if [[ "$VISIBILITY" != PUBLIC ]]; then
  echo "STOP: Repo visibility is $VISIBILITY, not PUBLIC" >&2
  exit 1
fi
bash packaging/build-deb.sh
if ! gh release view v1.0.0 --repo "$REPO" >/dev/null 2>&1; then
  gh release create v1.0.0 dist/btlink-wine_1.0.0_all.deb \
    --repo "$REPO" --title 'BTLink Wine Bridge 1.0.0' --notes-file CHANGELOG.md
fi
printf 'Release: https://github.com/%s/releases/tag/v1.0.0\n' "$REPO"
