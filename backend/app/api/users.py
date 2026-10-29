from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, VALID_ROLES
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List all user accounts (Admin only)",
)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all user accounts in the system. Requires Admin role."""
    users = db.query(User).order_by(User.id.asc()).all()
    return users


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account (Admin only)",
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new staff user with designated role. Requires Admin role."""
    # Check for duplicate username
    if db.query(User).filter(func.lower(User.username) == user_in.username.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_in.username}' is already registered.",
        )

    # Check for duplicate email
    if db.query(User).filter(func.lower(User.email) == user_in.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email address '{user_in.email}' is already registered.",
        )

    if user_in.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
        )

    new_user = User(
        username=user_in.username.strip(),
        email=user_in.email.strip().lower(),
        full_name=user_in.full_name.strip() if user_in.full_name else None,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active,
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating user account. Username or email already in use.",
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user account by ID",
)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve user details. Allowed for Admin or the user inspecting their own account."""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view other users' accounts.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a user account",
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user account attributes. Non-admins can only update their own password or full_name."""
    is_admin = current_user.role == "admin"
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify other users' accounts.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    # Non-admins cannot elevate role or change active status
    if not is_admin:
        if user_in.role is not None or user_in.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-administrators cannot alter account roles or activation status.",
            )

    if user_in.email is not None:
        email_clean = user_in.email.strip().lower()
        conflict = db.query(User).filter(
            func.lower(User.email) == email_clean,
            User.id != user_id,
        ).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email address '{email_clean}' is already registered to another user.",
            )
        user.email = email_clean

    if user_in.full_name is not None:
        user.full_name = user_in.full_name.strip()

    if user_in.password is not None:
        user.hashed_password = hash_password(user_in.password)

    if is_admin:
        is_target_active_admin = (user.role == "admin" and user.is_active is True)

        if user_in.role is not None:
            if user_in.role not in VALID_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
                )
            # Guard against demoting the last active administrator
            if is_target_active_admin and user_in.role != "admin":
                active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
                if active_admins <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Safety violation: Cannot demote the last active administrator.",
                    )
            user.role = user_in.role

        if user_in.is_active is not None:
            # Prevent admin from deactivating themselves
            if user.id == current_user.id and user_in.is_active is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Administrators cannot deactivate their own account.",
                )
            # Guard against deactivating the last active administrator
            if is_target_active_admin and user_in.is_active is False:
                active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
                if active_admins <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Safety violation: Cannot deactivate the last active administrator.",
                    )
            user.is_active = user_in.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user account (Admin only)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a user account. Requires Admin role. Self-deletion and removing last admin are blocked."""
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own account.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    # Guard against deleting the last active administrator
    if user.role == "admin" and user.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Safety violation: Cannot delete the last active administrator.",
            )

    db.delete(user)
    db.commit()
    return None
