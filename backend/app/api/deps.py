import hmac
from typing import Callable, Optional, Sequence
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# Optional HTTPBearer header extractor (auto_error=False allows falling back to cookies)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the authenticated user from either an HttpOnly cookie or Authorization Bearer header.
    
    Enforces Double-Submit CSRF token validation on state-changing requests when using cookie-based authentication.
    """
    token: Optional[str] = None
    used_cookie_auth = False

    # 1. Check Authorization: Bearer <token> header first (programmatic API clients / test suites)
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    # 2. Check HttpOnly cookie (interactive browser sessions)
    elif settings.COOKIE_NAME in request.cookies:
        token = request.cookies[settings.COOKIE_NAME]
        used_cookie_auth = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Enforce CSRF protection for cookie-authenticated state-changing requests
    if used_cookie_auth and request.method in ("POST", "PUT", "DELETE", "PATCH"):
        csrf_header = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
        if not csrf_header or not csrf_cookie or not hmac.compare_digest(csrf_header, csrf_cookie):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: State-changing requests using cookie authentication require a valid X-CSRF-Token header.",
            )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator.",
        )

    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """Dependency factory that verifies the current user possesses one of the specified roles.
    
    Returns 401 if unauthenticated.
    Returns 403 if authenticated but lacking the required role.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            roles_str = ", ".join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {roles_str}. Current role: {current_user.role}.",
            )
        return current_user

    return role_checker


# Convenient pre-configured role dependencies
require_admin = require_roles("admin")
require_manager_or_admin = require_roles("manager", "admin")
require_cashier_or_above = require_roles("cashier", "manager", "admin")
require_kitchen_or_above = require_roles("kitchen", "manager", "admin")
require_staff = require_roles("admin", "manager", "cashier", "kitchen")
