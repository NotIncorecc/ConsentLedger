"""
routers/auth.py — DigiLocker OAuth2 endpoints.

Flow:
  1. GET  /auth/digilocker/authorize  → redirect_url (send user here)
  2. GET  /auth/digilocker/callback   → exchange code → JWT session token
  3. GET  /auth/digilocker/identity   → return ZK-safe identity (age + identity_secret)
     (requires Authorization: Bearer <jwt>)

MOCK MODE: When DIGILOCKER_CLIENT_ID is unset a mock callback URL is used and
the identity endpoint returns synthetic data. Convenient for development.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings
from services.digilocker import DigiLockerService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/digilocker", tags=["auth"])

# ──────────────────────── Singleton ───────────────────────────────────────

_digilocker = DigiLockerService(
    client_id=settings.digilocker_client_id,
    client_secret=settings.digilocker_client_secret,
    redirect_uri=settings.digilocker_redirect_uri,
    app_secret=settings.app_secret,
)

# ──────────────────────── JWT helpers ─────────────────────────────────────


def _create_jwt(payload: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {**payload, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session token: {exc}",
        ) from exc


def _get_current_identity(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token.")
    return _decode_jwt(auth[7:])


# ──────────────────────── Endpoints ───────────────────────────────────────


class AuthorizeResponse(BaseModel):
    redirect_url: str
    state: str


@router.get("/authorize", response_model=AuthorizeResponse, summary="Get DigiLocker OAuth redirect URL")
async def authorize():
    """
    Returns the URL the frontend should redirect the user to for DigiLocker
    authentication. The `state` parameter is a random nonce for CSRF protection.
    """
    state = secrets.token_urlsafe(16)
    redirect_url = _digilocker.get_auth_url(state)
    return AuthorizeResponse(redirect_url=redirect_url, state=state)


@router.get("/callback", summary="DigiLocker OAuth callback — exchange code for session")
async def callback(code: str = Query(...), state: str = Query(default="")):
    """
    DigiLocker redirects here after authentication.
    Exchanges the auth code for an access token, fetches Aadhaar identity data,
    derives ZK-safe values, and returns a short-lived JWT session token.
    """
    token_data = await _digilocker.exchange_code(code)
    access_token = token_data.get("access_token", "")

    identity = await _digilocker.get_identity_for_zk(access_token)

    session_jwt = _create_jwt(
        {
            "age": identity["age"],
            "identity_secret": identity["identity_secret"],
            "state": state,
        }
    )
    return JSONResponse(
        content={
            "session_token": session_jwt,
            "age_verified": identity["age"] >= 18,
            "message": "DigiLocker authentication successful.",
        }
    )


@router.get("/mock-callback", summary="Mock DigiLocker callback for development")
async def mock_callback(state: str = Query(default="")):
    """
    Development-only endpoint. Returns a synthetic session token without
    real DigiLocker credentials. Never use in production.
    """
    identity = _digilocker._mock_identity()
    session_jwt = _create_jwt(
        {
            "age": identity["age"],
            "identity_secret": identity["identity_secret"],
            "state": state,
            "is_mock": True,
        }
    )
    return JSONResponse(
        content={
            "session_token": session_jwt,
            "age_verified": True,
            "message": "Mock DigiLocker session created (development only).",
        }
    )


class IdentityResponse(BaseModel):
    age: int
    identity_secret: str
    age_verified: bool
    is_mock: bool = False


@router.get(
    "/identity",
    response_model=IdentityResponse,
    summary="Return ZK-safe identity from session token",
)
async def get_identity(
    identity: Annotated[dict, Depends(_get_current_identity)],
):
    """
    Returns the age and identity_secret stored in the session JWT so the
    frontend can pass them to the ZK proof generation endpoints.

    The identity_secret is a one-way HMAC derivation — safe to expose to the
    frontend since the raw Aadhaar UID cannot be recovered from it.
    """
    return IdentityResponse(
        age=identity.get("age", 0),
        identity_secret=identity.get("identity_secret", ""),
        age_verified=identity.get("age", 0) >= 18,
        is_mock=identity.get("is_mock", False),
    )
