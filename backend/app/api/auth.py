import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserResponse

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login with credentials",
)
def login(
    login_in: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate user credentials, set secure HttpOnly cookie, and return signed token."""
    login_ident = login_in.username.strip().lower()

    # Generic error detail to prevent account enumeration
    invalid_creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(User).filter(
        (func.lower(User.username) == login_ident) | (func.lower(User.email) == login_ident)
    ).first()

    if not user:
        raise invalid_creds_exc

    if not verify_password(login_in.password, user.hashed_password):
        raise invalid_creds_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact an administrator.",
        )

    # Issue signed JWT with standard claims
    token_claims = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
    }
    access_token = create_access_token(token_claims)

    # Generate random CSRF token for Double-Submit cookie defense
    csrf_token = secrets.token_urlsafe(32)

    # 1. Set secure HttpOnly cookie for session token
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    # 2. Set readable CSRF cookie for client-side inclusion in X-CSRF-Token header
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        csrf_token=csrf_token,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the profile of the currently authenticated user."""
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and clear session cookie",
)
def logout(response: Response):
    """Clear session and CSRF cookies on the client."""
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
    )
    return {"message": "Successfully logged out."}
