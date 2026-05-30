from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth.jwt import authenticate_user, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest) -> TokenResponse:
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=user["sub"], role=user["role"])
    return TokenResponse(access_token=token)
