import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import calendar, notes, recording

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.getenv("TRANSCRIPT_DIR", ""), exist_ok=True)
    os.makedirs(os.getenv("NOTES_DIR", ""), exist_ok=True)
    os.makedirs("/tmp/meeting-recordings", exist_ok=True)
    yield


app = FastAPI(title="Meeting Note-Taker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recording.router, prefix="/api/recording")
app.include_router(calendar.router, prefix="/api/calendar")
app.include_router(notes.router, prefix="/api/notes")


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/config")
async def config():
    """Return non-secret config values the frontend needs."""
    return {
        "obsidian_vault_name": os.getenv("OBSIDIAN_VAULT_NAME", ""),
        "obsidian_notes_subpath": os.getenv("OBSIDIAN_NOTES_SUBPATH", ""),
    }
