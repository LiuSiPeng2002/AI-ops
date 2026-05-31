"""User management API: CRUD + role assignment (admin+ only)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.security import hash_password
from database import get_db
from models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="viewer")
    email: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    email: str | None = None
    password: str | None = None
    status: str | None = None


VALID_ROLES = {"viewer", "operator", "admin", "superadmin"}


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin or superadmin required")


@router.get("")
async def list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin+ only)."""
    _require_admin(current_user)

    total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    users = (await db.execute(
        select(User).offset(offset).limit(limit).order_by(User.id)
    )).scalars().all()

    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "email": u.email,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
    }


@router.post("")
async def create_user(
    body: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin+ only)."""
    _require_admin(current_user)
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {VALID_ROLES}")

    existing = (await db.execute(
        select(User).where(User.username == body.username)
    )).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        email=body.email,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"status": "ok", "user_id": user.id}


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user role/status/password (admin+ only). Only superadmin can modify admins."""
    _require_admin(current_user)

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Only superadmin can modify admin users
    if user.role in ("admin", "superadmin") and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can modify admin users")

    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        user.role = body.role
    if body.email is not None:
        user.email = body.email
    if body.status is not None:
        if body.status not in ("active", "disabled"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'disabled'")
        user.status = body.status
    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password too short")
        user.password_hash = hash_password(body.password)

    await db.commit()
    return {"status": "ok"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (superadmin only)."""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"status": "ok"}
