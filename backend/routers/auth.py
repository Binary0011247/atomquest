import os
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, get_password_hash, verify_password
from cache import invalidate_mutation_caches
from database import get_db
from models import User, UserRole
from schemas import (
    GoogleAuthUrlResponse,
    GoogleCallbackResponse,
    SeedResponse,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _google_client_secret() -> str:
    return os.getenv("GOOGLE_CLIENT_SECRET", "").strip()


def _google_redirect_uri() -> str:
    return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback").strip()


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
    )


@router.get("/google/login", response_model=GoogleAuthUrlResponse)
def google_login():
    client_id = _google_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return GoogleAuthUrlResponse(auth_url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback", response_model=GoogleCallbackResponse)
def google_callback(
    code: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
):
    client_id = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri = _google_redirect_uri()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    try:
        with httpx.Client(timeout=15.0) as client:
            token_res = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_res.raise_for_status()
            access_token_google = token_res.json().get("access_token")
            if not access_token_google:
                raise HTTPException(status_code=400, detail="Failed to obtain Google token")

            user_res = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token_google}"},
            )
            user_res.raise_for_status()
            profile = user_res.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {exc}",
        ) from exc

    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    user = db.query(User).filter(User.email == email).first()
    is_new_user = False
    if not user:
        is_new_user = True
        user = User(
            name=profile.get("name") or email.split("@")[0],
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            role=UserRole.employee,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        invalidate_mutation_caches(goals=True)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    access_token = create_access_token({"sub": str(user.id)})
    return GoogleCallbackResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
        is_new_user=is_new_user,
    )


@router.post("/seed", response_model=SeedResponse)
def seed_users(db: Annotated[Session, Depends(get_db)]):
    from demo_service import seed_demo_users

    created_emails = seed_demo_users(db)
    invalidate_mutation_caches(goals=True)
    return SeedResponse(message="Seeded successfully", users=created_emails)


@router.get("/me", response_model=UserPublic)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return UserPublic.model_validate(current_user)
