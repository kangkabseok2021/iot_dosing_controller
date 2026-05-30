from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config import settings

USERS: dict[str, tuple[str, str]] = {
    "dispatcher1": ("dispatch123", "dispatcher"),
    "viewer1": ("viewer123", "viewer"),
}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS.get(username)
    if not user or user[0] != password:
        return None
    return {"sub": username, "role": user[1]}


def create_access_token(sub: str, role: str) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
