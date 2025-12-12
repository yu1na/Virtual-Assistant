"""Utility helpers for report API endpoints."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.user.models import User
from app.domain.user.repository import UserRepository


def resolve_owner_name(
    db: Session,
    current_user: User | None,
    owner: str | None,
    owner_id: int | None,
) -> str:
    """
    Resolve the owner name using the precedence rules:
    1) authenticated user
    2) owner_id lookup
    3) owner string from request
    """
    if current_user and current_user.name:
        return current_user.name

    if owner_id is not None:
        user = UserRepository(db).get_by_id(owner_id)
        if not user or not user.name:
            raise HTTPException(status_code=400, detail="Invalid owner_id")
        return user.name

    if owner:
        return owner

    raise HTTPException(status_code=400, detail="owner or owner_id required")
