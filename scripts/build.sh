#!/bin/bash
# Build script for Meeting Note-Taker macOS app
# Produces: dist/Meeting Note-Taker.dmg
#
# Prerequisites:
#   - Python 3.12+ with venv set up in backend/
#   - Node.js 18+ with npm
#   - Xcode Command Line Tools (for Swift)
#   - PyInstaller: pip install pyinstaller
#
# Usage:
#   chmod +x scripts/build.sh
#   ./scripts/build.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "=== Step 1: Build AudioTee (system audio capture) ==="
if [ ! -d "$ROOT_DIR/vendor/audiotee" ]; then
    echo "  Cloning AudioTee..."
    git clone https://github.com/makeusabrew/audiotee.git "$ROOT_DIR/vendor/audiotee"
fi
cd "$ROOT_DIR/vendor/audiotee"
swift build -c release 2>&1 | tail -1
mkdir -p "$BACKEND_DIR/bin"
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    cp .build/arm64-apple-macosx/release/audiotee "$BACKEND_DIR/bin/audiotee"
else
    cp .build/x86_64-apple-macosx/release/audiotee "$BACKEND_DIR/bin/audiotee"
fi
echo "✓ AudioTee built to backend/bin/audiotee"

echo ""
echo "=== Step 2: Build Python backend with PyInstaller ==="
cd "$BACKEND_DIR"
source venv/bin/activate
pip install pyinstaller
pyinstaller meeting-note-taker.spec --noconfirm
deactivate
echo "✓ Backend built to $BACKEND_DIR/dist/meeting-note-taker-backend/"

echo ""
echo "=== Step 3: Install Electron dependencies ==="
cd "$FRONTEND_DIR"
npm install
echo "✓ Dependencies installed"

echo ""
echo "=== Step 4: Package Electron app ==="
npm run build
echo "✓ App packaged to $ROOT_DIR/dist/"

echo ""
echo "=== Done! ==="
echo "Your .dmg is in: $ROOT_DIR/dist/"
ls -lh "$ROOT_DIR/dist/"*.dmg 2>/dev/null || echo "(no .dmg found — check output above for errors)"
