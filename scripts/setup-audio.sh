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

# Install BlackHole
echo "Checking BlackHole 2ch..."
if brew list blackhole-2ch &> /dev/null 2>&1; then
    echo "  BlackHole 2ch is already installed."
else
    echo "  Installing BlackHole 2ch..."
    brew install blackhole-2ch
    echo "  BlackHole 2ch installed."
fi

# Install PortAudio
echo "Checking PortAudio..."
if brew list portaudio &> /dev/null 2>&1; then
    echo "  PortAudio is already installed."
else
    echo "  Installing PortAudio..."
    brew install portaudio
    echo "  PortAudio installed."
fi

echo ""
echo "=== Audio devices available ==="
# Quick Python check for audio devices
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"

if [ -f "$BACKEND_DIR/venv/bin/python" ]; then
    "$BACKEND_DIR/venv/bin/python" -c "
import pyaudio
p = pyaudio.PyAudio()
print()
blackhole_found = False
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        marker = ''
        if 'blackhole' in info['name'].lower():
            marker = '  <-- BlackHole'
            blackhole_found = True
        print(f\"  [{i}] {info['name']} ({info['maxInputChannels']}ch){marker}\")
p.terminate()
print()
if blackhole_found:
    print('BlackHole detected as an audio input device.')
else:
    print('WARNING: BlackHole was NOT detected as an audio input device.')
    print('You may need to restart your computer after installing BlackHole.')
" 2>/dev/null || echo "  (Could not list devices - Python venv may not be set up yet)"
else
    echo "  (Python venv not set up yet - run setup first)"
fi

echo ""
echo "=== MANUAL STEP REQUIRED ==="
echo ""
echo "You must create a Multi-Output Device in Audio MIDI Setup:"
echo ""
echo "  1. Open 'Audio MIDI Setup' (search in Spotlight)"
echo "  2. Click the '+' button at the bottom-left"
echo "  3. Select 'Create Multi-Output Device'"
echo "  4. Check BOTH your speakers/headphones AND 'BlackHole 2ch'"
echo "  5. Rename it to 'Meeting Recorder' (optional but helpful)"
echo ""
echo "Before each meeting, set your system output to this Multi-Output Device."
echo "This ensures you hear the audio AND the app can capture it."
echo ""
echo "Setup complete!"
