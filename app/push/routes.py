"""HTTP API for phone reminders about due patterns ("Przypomnienia na telefonie")."""

import asyncio
import time as monotonic_clock
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_member_id
from ..config import settings
from ..db import get_db
from ..db.models import UserDB
from . import service

router = APIRouter(prefix="/api/push", tags=["push"])

DISABLED = "Przypomnienia na telefonie są wyłączone."
BAD_ENDPOINT = "Ta przeglądarka używa usługi powiadomień, której nie obsługujemy."
BAD_KEYS = "Przeglądarka przekazała niepoprawne dane powiadomień. Wyłącz i włącz powiadomienia ponownie."
BAD_TIME = "Wybierz godzinę między 6:00 a 21:00 (co 5 minut)."
ENDPOINT_TAKEN = "To urządzenie ma włączone przypomnienia na innym koncie. Wyłącz je tam albo wyłącz i włącz powiadomienia w przeglądarce."
NO_DEVICE = "Najpierw włącz przypomnienia na tym urządzeniu."
TEST_TOO_SOON = "Poczekaj chwilę przed kolejnym próbnym powiadomieniem."
TEST_COOLDOWN_SECONDS = 30

# user_id -> monotonic time of the last test notification (single worker)
_last_test: dict[str, float] = {}


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1024)
    keys: SubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(max_length=1024)


class ReminderTimesIn(BaseModel):
    weekday_time: str = Field(max_length=5)
    weekend_time: str = Field(max_length=5)


def _require_enabled() -> None:
    if not service.enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, DISABLED)


def _config(db: Session, user_id: str) -> dict:
    times = service.times_for(db, user_id)
    return {
        "enabled": service.enabled(),
        "public_key": settings.vapid_public_key if service.enabled() else None,
        "weekday_time": times.weekday_time,
        "weekend_time": times.weekend_time,
        "devices": len(service.subscriptions_of(db, user_id)),
    }


@router.get("/config")
async def get_config(request: Request, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    return _config(db, user_id)


@router.post("/subscriptions")
async def subscribe(request: Request, payload: SubscriptionIn, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    _require_enabled()
    if not service.valid_endpoint(payload.endpoint):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BAD_ENDPOINT)
    if not service.valid_keys(payload.keys.p256dh, payload.keys.auth):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BAD_KEYS)
    try:
        service.subscribe(db, user_id, payload.endpoint, payload.keys.p256dh, payload.keys.auth)
    except service.EndpointTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, ENDPOINT_TAKEN)
    return _config(db, user_id)


@router.post("/subscriptions/delete")
async def unsubscribe(request: Request, payload: UnsubscribeIn, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    service.unsubscribe(db, user_id, payload.endpoint)
    return _config(db, user_id)


@router.put("/settings")
async def save_settings(request: Request, payload: ReminderTimesIn, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    weekday = service.parse_slot(payload.weekday_time)
    weekend = service.parse_slot(payload.weekend_time)
    if not weekday or not weekend:
        raise HTTPException(422, BAD_TIME)
    service.save_times(db, user_id, weekday, weekend)
    return _config(db, user_id)


@router.post("/test")
async def send_test(request: Request, db: Session = Depends(get_db)):
    """A sample notification to every device of this user."""
    user_id = await current_member_id(request)
    _require_enabled()
    user = db.get(UserDB, user_id)
    subscriptions = service.live_subscriptions(db, user) if user else []
    if not subscriptions:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_DEVICE)
    now = monotonic_clock.monotonic()
    if now - _last_test.get(user_id, -TEST_COOLDOWN_SECONDS) < TEST_COOLDOWN_SECONDS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TEST_TOO_SOON)
    _last_test[user_id] = now
    counts = await asyncio.to_thread(service.deliver, db, subscriptions, service.TEST_PAYLOAD, service.send)
    return {"sent": counts[service.OK], "failed": counts[service.FAILED] + counts[service.GONE]}
