# Meeting Note-Taker

Electron desktop app that records meeting audio, transcribes it via Google Gemini, generates structured Obsidian notes, and uploads them to Google Drive.

## What it does

1. Reads your Google Calendar to detect the current meeting and attendees
2. Records audio input (mic) and system audio output (via [AudioTee](https://github.com/makeusabrew/audiotee) / Core Audio Taps)
3. Transcribes the recording using Gemini 2.5 Flash
4. Saves the raw transcript as a `.md` file in your Obsidian vault
5. Generates structured notes (attendees, purpose, challenges, goals, next steps)
6. Saves the structured notes as a `.md` file with a wiki-link to the transcript
7. Uploads the notes to Google Drive as a Google Doc

## Installation (macOS app)

### Download

Download the latest `.dmg` from the [Releases](../../releases) page, open it, and drag **Meeting Note-Taker** to your Applications folder.

> **Note**: The app is unsigned. On first launch, right-click the app and choose "Open", then click "Open" in the dialog. macOS will remember your choice.

### First launch

The app will open to the **Settings** page. You'll need to configure:

1. **Gemini API Key** — get one free at [Google AI Studio](https://aistudio.google.com/apikey)
2. **Google OAuth credentials** — follow the [Google Cloud Setup](#google-cloud-setup) guide below, then upload your `credentials.json` file
3. **Obsidian paths** — tell the app where your Obsidian vault lives

Once configured, click **Done** to start using the app.

### Permissions

On first recording, macOS will prompt for **Screen & System Audio Recording** permission. This is required by the Core Audio Taps API to capture system audio. Grant permission in:

**System Settings → Privacy & Security → Screen & System Audio Recording**

> Your volume keys and default audio output work normally — no virtual audio devices or Multi-Output Device setup needed.

## Prerequisites

- **macOS 14.2+** (Sonoma or later) — required for Core Audio Taps API
- [Obsidian](https://obsidian.md/) installed with a vault set up

## Google Cloud Setup

1. Create a project at https://console.cloud.google.com/
2. Enable **Google Calendar API** and **Google Drive API** (APIs & Services > Library)
3. Configure the OAuth consent screen (APIs & Services > OAuth consent screen):
   - Select External, fill in app name and emails
   - Add scopes: `calendar.readonly` and `drive.file`
   - Add yourself as a test user
4. Create OAuth credentials (APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app)
5. Download the JSON — this is your `credentials.json` to upload in the app's Settings

## Development Setup

If you want to run from source instead of the packaged app:

### 1. System dependencies

```bash
brew install portaudio  # required by PyAudio for mic capture
```

### 2. Build AudioTee

AudioTee captures system audio using Apple's Core Audio Taps API. Build it from source:

```bash
# The setup script handles this automatically:
./scripts/setup-audio.sh

# Or manually:
git clone https://github.com/makeusabrew/audiotee.git vendor/audiotee
cd vendor/audiotee && swift build -c release
mkdir -p backend/bin
cp .build/arm64-apple-macosx/release/audiotee backend/bin/audiotee
```

### 3. Python backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 4. Electron frontend

```bash
cd frontend
npm install
```

### 5. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in:

- `GEMINI_API_KEY` — get from https://aistudio.google.com/app/apikey
- `TRANSCRIPT_DIR` — absolute path to a folder in your Obsidian vault for raw transcripts
- `NOTES_DIR` — absolute path to a folder in your Obsidian vault for structured notes
- `OBSIDIAN_VAULT_NAME` — your vault's name as shown in Obsidian's vault switcher
- `OBSIDIAN_NOTES_SUBPATH` — relative path from vault root to the notes folder (e.g., `MeetingNotes/notes`)

Example paths for a vault called `my_notes` at `~/Documents/Obsidian/my_notes/`:
```
TRANSCRIPT_DIR=/Users/you/Documents/Obsidian/my_notes/MeetingNotes/transcripts
NOTES_DIR=/Users/you/Documents/Obsidian/my_notes/MeetingNotes/notes
OBSIDIAN_VAULT_NAME=my_notes
OBSIDIAN_NOTES_SUBPATH=MeetingNotes/notes
```

The `transcripts` and `notes` directories will be created automatically on first run.

### 6. Running in dev mode

```bash
cd frontend
npm start
```

This launches Electron, which automatically starts the Python backend on port 8000. On first run, a browser window opens for Google OAuth consent.

## Building the macOS App

To package the app as a `.dmg`:

```bash
./scripts/build.sh
```

The build script:
1. Clones and compiles AudioTee (Swift → native binary)
2. Compiles the Python backend into a standalone binary with PyInstaller (AudioTee is bundled inside)
3. Installs Electron dependencies
4. Packages everything into a `.dmg` with Electron Builder

Output: `dist/Meeting Note-Taker.dmg`

## How audio capture works

The app captures two audio streams simultaneously:

- **Microphone**: via PyAudio (default system mic, unchanged)
- **System audio**: via [AudioTee](https://github.com/makeusabrew/audiotee), a Swift CLI that uses Apple's Core Audio Taps API (macOS 14.2+) to intercept audio from all running processes

Both streams are mixed into a single WAV file using numpy. Your system audio output is **not modified** — no virtual audio devices, no Multi-Output Device, and your volume keys work normally throughout.

If AudioTee is not available, the app gracefully falls back to mic-only recording.

## Output locations

- **Transcripts**: the path you set in `TRANSCRIPT_DIR` (or via Settings)
- **Notes**: the path you set in `NOTES_DIR` (or via Settings)
- **Google Drive**: `My Drive/<DRIVE_FOLDER_NAME>/` (as Google Docs, default folder name is `notes`)

Clicking a note in the app's "Recent Notes" list opens it directly in Obsidian.

## Architecture

```
Electron (main.js)
  → spawns Python backend (FastAPI on localhost:8000)
     - Dev: venv/bin/python + uvicorn
     - Packaged: PyInstaller binary in app resources
  → BrowserWindow (renderer.js)
       → fetch() to http://localhost:8000/api/*

Audio capture:
  - Mic: PyAudio (default input device)
  - System: AudioTee subprocess (Core Audio Taps → raw PCM via stdout)
  - Mixed with numpy → single WAV file → Gemini transcription
```

## Configuration

All configuration can be set via the in-app **Settings** page, or manually in `backend/.env` (see `backend/.env.example` for a template):

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GOOGLE_CREDENTIALS_PATH` | Path to OAuth credentials JSON (default: `./credentials.json`) |
| `GOOGLE_TOKEN_PATH` | Path to cached OAuth token (default: `./token.json`, auto-created on first auth) |
| `TRANSCRIPT_DIR` | Absolute path for raw transcript `.md` files |
| `NOTES_DIR` | Absolute path for structured note `.md` files |
| `DRIVE_FOLDER_NAME` | Google Drive folder name for uploads (default: `notes`) |
| `OBSIDIAN_VAULT_NAME` | Obsidian vault name (for opening notes via `obsidian://` URI) |
| `OBSIDIAN_NOTES_SUBPATH` | Path from vault root to notes folder (for `obsidian://` URI) |
