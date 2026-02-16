# Meeting Note-Taker

Electron desktop app that records meeting audio, transcribes it via Google Gemini, generates structured Obsidian notes, and uploads them to Google Drive.

## What it does

1. Reads your Google Calendar to detect the current meeting and attendees
2. Records audio input (mic) and output (system audio via BlackHole)
3. Transcribes the recording using Gemini 2.5 Flash
4. Saves the raw transcript as a `.md` file in your Obsidian vault
5. Generates structured notes (attendees, purpose, challenges, goals, next steps)
6. Saves the structured notes as a `.md` file with a wiki-link to the transcript
7. Uploads the notes to Google Drive as a Google Doc

## Prerequisites

- macOS (required for BlackHole audio capture)
- [Obsidian](https://obsidian.md/) installed with a vault set up
- Python 3.12+
- Node.js 20+
- Homebrew

## Setup

### 1. System dependencies

```bash
brew install blackhole-2ch  # requires sudo
brew install portaudio
```

After installing BlackHole, open **Audio MIDI Setup** (search Spotlight), click **+**, select **Create Multi-Output Device**, and check both your speakers and **BlackHole 2ch**. Set this as your system output before recording.

### 2. Google Cloud project

1. Create a project at https://console.cloud.google.com/
2. Enable **Google Calendar API** and **Google Drive API** (APIs & Services > Library)
3. Configure the OAuth consent screen (APIs & Services > OAuth consent screen):
   - Select External, fill in app name and emails
   - Add scopes: `calendar.readonly` and `drive.file`
   - Add yourself as a test user
4. Create OAuth credentials (APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app)
5. Download the JSON and save it as `backend/credentials.json`

### 3. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in:

- `GEMINI_API_KEY` -- get from https://aistudio.google.com/app/apikey
- `TRANSCRIPT_DIR` -- absolute path to a folder in your Obsidian vault for raw transcripts
- `NOTES_DIR` -- absolute path to a folder in your Obsidian vault for structured notes
- `OBSIDIAN_VAULT_NAME` -- your vault's name as shown in Obsidian's vault switcher
- `OBSIDIAN_NOTES_SUBPATH` -- relative path from vault root to the notes folder (e.g., `MeetingNotes/notes`)

Example paths for a vault called `my_notes` at `~/Documents/Obsidian/my_notes/`:
```
TRANSCRIPT_DIR=/Users/you/Documents/Obsidian/my_notes/MeetingNotes/transcripts
NOTES_DIR=/Users/you/Documents/Obsidian/my_notes/MeetingNotes/notes
OBSIDIAN_VAULT_NAME=my_notes
OBSIDIAN_NOTES_SUBPATH=MeetingNotes/notes
```

The `transcripts` and `notes` directories will be created automatically on first run.

### 4. Python backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 5. Electron frontend

```bash
cd frontend
npm install
```

## Running

```bash
cd frontend
npm start
```

This launches Electron, which automatically starts the Python backend on port 8000. On first run, a browser window opens for Google OAuth consent.

## Output locations

- **Transcripts**: the path you set in `TRANSCRIPT_DIR`
- **Notes**: the path you set in `NOTES_DIR`
- **Google Drive**: `My Drive/<DRIVE_FOLDER_NAME>/` (as Google Docs, default folder name is `notes`)

Clicking a note in the app's "Recent Notes" list opens it directly in Obsidian.

## Architecture

```
Electron (main.js)
  -> spawns Python (FastAPI on localhost:8000)
  -> BrowserWindow (renderer.js)
       -> fetch() to http://localhost:8000/api/*
```

The backend handles audio recording, Gemini API calls, file I/O, and Google API interactions. The frontend provides a minimal UI with start/stop controls, meeting info, and a recent notes list.

## Configuration

All configuration is in `backend/.env` (see `backend/.env.example` for a template):

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
