#!/usr/bin/env bash
# Build all workspace distributions including the latest console frontend.
# Run from repo root: bash scripts/wheel_build.sh
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONSOLE_DIR="$REPO_ROOT/console"
CONSOLE_DEST="$REPO_ROOT/packages/minions-app/src/minions/console"

echo "[wheel_build] Building console frontend..."
(cd "$CONSOLE_DIR" && npm ci)
(cd "$CONSOLE_DIR" && npm run build)

echo "[wheel_build] Copying console/dist/* -> packages/minions-app/src/minions/console/..."
rm -rf "$CONSOLE_DEST"/*

mkdir -p "$CONSOLE_DEST"
cp -R "$CONSOLE_DIR/dist/"* "$CONSOLE_DEST/"

echo "[wheel_build] Bundling website docs into package..."
DOCS_SRC="$REPO_ROOT/website/public/docs"
DOCS_DEST="$REPO_ROOT/packages/minions-app/src/minions/docs"
rm -rf "$DOCS_DEST"
mkdir -p "$DOCS_DEST"
cp "$DOCS_SRC/"*.md "$DOCS_DEST/"

echo "[wheel_build] Building 14 wheels + sdists..."
python3 -m pip install --quiet build
python3 scripts/build_workspace.py

echo "[wheel_build] Done. Workspace artifacts in: $REPO_ROOT/dist/"
