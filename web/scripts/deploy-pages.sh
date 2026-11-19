#!/usr/bin/env bash
# Build the site and publish web/dist to the gh-pages branch (served by GitHub Pages).
# In GitHub Actions, set DEPLOY_REMOTE to an authenticated URL; locally the repo's origin is used.
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build
REMOTE="${DEPLOY_REMOTE:-$(git -C .. remote get-url origin)}"
NAME="$(git -C .. config user.name || true)"
EMAIL="$(git -C .. config user.email || true)"
NAME="${NAME:-github-actions[bot]}"
EMAIL="${EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
SHA="$(git -C .. rev-parse --short HEAD)"
cd dist
touch .nojekyll            # serve files as-is (no Jekyll processing)
cp index.html 404.html     # unknown paths fall back to the app
rm -rf .git
git init -q -b gh-pages
git add -A
git -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "Deploy $SHA"
git push -q -f "$REMOTE" gh-pages
rm -rf .git
echo "Published to gh-pages"
