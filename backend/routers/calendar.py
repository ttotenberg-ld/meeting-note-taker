import os

from fastapi import APIRouter

from services.calendar_service import CalendarService
from services.google_auth import get_credentials

router = APIRouter()


def _get_calendar_service() -> CalendarService | None:
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "./token.json")
    if not os.path.exists(creds_path):
        return None
    creds = get_credentials(creds_path, token_path)
    return CalendarService(creds)


@router.get("/current-meeting")
async def current_meeting():
    try:
        cal_service = _get_calendar_service()
        if not cal_service:
            return {"meeting": None, "error": "Google credentials not configured"}
        meeting = cal_service.get_current_meeting()
        return {"meeting": meeting}
    except Exception as e:
        return {"meeting": None, "error": str(e)}


@router.get("/upcoming")
async def upcoming_meetings():
    try:
        cal_service = _get_calendar_service()
        if not cal_service:
            return {"meetings": [], "error": "Google credentials not configured"}
        meetings = cal_service.get_upcoming_meetings()
        return {"meetings": meetings}
    except Exception as e:
        return {"meetings": [], "error": str(e)}
