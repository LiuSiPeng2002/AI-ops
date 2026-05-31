from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.security import create_access_token, create_refresh_token, hash_password, verify_password, verify_token
from database import get_db
from models.user import User
from schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    payload = verify_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    token_data = {"sub": payload["sub"], "username": payload["username"], "role": payload["role"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
async def change_password(
    body: "ChangePasswordRequest",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Self-service password change (any authenticated user)."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"status": "ok"}


@router.post("/register", response_model=UserInfo)
async def register(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == request.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    user = User(username=request.username, password_hash=hash_password(request.password), role="operator")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
