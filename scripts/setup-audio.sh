#!/bin/bash
# Setup script for Meeting Note-Taker audio requirements
# Run this once before using the app

set -e

echo "=== Meeting Note-Taker Audio Setup ==="
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "ERROR: Homebrew is not installed. Install it from https://brew.sh"
    exit 1
fi

# Install PortAudio (needed by PyAudio for mic capture)
echo "Checking PortAudio..."
if brew list portaudio &> /dev/null 2>&1; then
    echo "  PortAudio is already installed."
else
    echo "  Installing PortAudio..."
    brew install portaudio
    echo "  PortAudio installed."
fi

# Build AudioTee if not already present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
AUDIOTEE_BIN="$ROOT_DIR/backend/bin/audiotee"

echo ""
echo "Checking AudioTee (system audio capture)..."
if [ -f "$AUDIOTEE_BIN" ]; then
    echo "  AudioTee binary already exists at backend/bin/audiotee"
else
    echo "  Building AudioTee from vendor/audiotee..."
    if [ ! -d "$ROOT_DIR/vendor/audiotee" ]; then
        echo "  Cloning AudioTee..."
        git clone https://github.com/makeusabrew/audiotee.git "$ROOT_DIR/vendor/audiotee"
    fi
    cd "$ROOT_DIR/vendor/audiotee"
    swift build -c release 2>&1 | tail -1
    mkdir -p "$ROOT_DIR/backend/bin"

    # Detect architecture and copy the right binary
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        cp .build/arm64-apple-macosx/release/audiotee "$AUDIOTEE_BIN"
    else
        cp .build/x86_64-apple-macosx/release/audiotee "$AUDIOTEE_BIN"
    fi
    cd "$ROOT_DIR"
    echo "  AudioTee built and copied to backend/bin/audiotee"
fi

echo ""
echo "=== Audio devices available ==="
BACKEND_DIR="$ROOT_DIR/backend"

if [ -f "$BACKEND_DIR/venv/bin/python" ]; then
    "$BACKEND_DIR/venv/bin/python" -c "
import pyaudio
p = pyaudio.PyAudio()
print()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"  [{i}] {info['name']} ({info['maxInputChannels']}ch)\")
p.terminate()
" 2>/dev/null || echo "  (Could not list devices - Python venv may not be set up yet)"
else
    echo "  (Python venv not set up yet - run setup first)"
fi

echo ""
echo "=== Permissions ==="
echo ""
echo "On first recording, macOS will ask for Screen Recording permission."
echo "This is required by AudioTee to capture system audio."
echo ""
echo "Go to: System Settings > Privacy & Security > Screen & System Audio Recording"
echo "and allow your terminal app (or Meeting Note-Taker.app)."
echo ""
echo "Your volume keys and default audio output remain unchanged —"
echo "no Multi-Output Device or BlackHole needed!"
echo ""
echo "Setup complete!"
