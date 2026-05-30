from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token

# auto_error=False lets us control the exact status code for missing credentials
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        return decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_dispatcher(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "dispatcher":
        raise HTTPException(status_code=403, detail="Dispatcher role required")
    return user
