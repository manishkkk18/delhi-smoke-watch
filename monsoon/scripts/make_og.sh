#!/usr/bin/env bash
# Render og.html to ../og.png (1200x630) with a headless Chromium browser (Chrome or Edge).
set -euo pipefail
cd "$(dirname "$0")"
BROWSER="${BROWSER:-$(command -v google-chrome || command -v chromium || echo "/c/Program Files/Google/Chrome/Application/chrome.exe")}"
"$BROWSER" --headless=new --disable-gpu --hide-scrollbars --window-size=1200,630 --virtual-time-budget=5000 \
  --screenshot="$(pwd)/../og.png" "file:///$(pwd -W 2>/dev/null || pwd)/og.html"
echo "wrote ../og.png"
