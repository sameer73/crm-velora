import re
import secrets
from datetime import timedelta

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import SessionToken, Shop, User, UserShop, utcnow

SESSION_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def clean_username(value: str) -> str:
    username = (value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,60}", username):
        raise AppError("Username must be 3–60 letters or numbers")
    return username


def clean_password(value: str) -> str:
    password = value or ""
    if len(password) < 6:
        raise AppError("Password must be at least 6 characters")
    if len(password) > 100:
        raise AppError("Password is too long")
    return password


def clean_text(value: str, label: str, required: bool = True, limit: int = 120) -> str:
    text = " ".join((value or "").split())
    if required and not text:
        raise AppError(f"Enter a {label.lower()}")
    if len(text) > limit:
        raise AppError(f"{label} is too long")
    return text


def needs_setup(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(User)) == 0


def user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.lower()))


def start_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        SessionToken(
            token=token,
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    db.flush()
    return token


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = db.get(SessionToken, token)
    if row is None:
        return None
    if row.expires_at < utcnow():
        db.delete(row)
        db.commit()
        return None
    return db.get(User, row.user_id)


def end_session(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.get(SessionToken, token)
    if row is not None:
        db.delete(row)
        db.commit()


def shops_for(db: Session, user: User) -> list[Shop]:
    if user.role == "owner":
        return list(db.scalars(select(Shop).order_by(Shop.name, Shop.id)))
    return list(
        db.scalars(
            select(Shop)
            .join(UserShop, UserShop.shop_id == Shop.id)
            .where(UserShop.user_id == user.id)
            .order_by(Shop.name, Shop.id)
        )
    )


def shop_ids_for(db: Session, user: User) -> list[int]:
    return [shop.id for shop in shops_for(db, user)]


def require_shop(db: Session, user: User, shop_id: int) -> Shop:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise AppError("Shop not found", 404)
    if user.role != "owner" and db.get(UserShop, (user.id, shop_id)) is None:
        raise AppError("You cannot use this shop", 403)
    return shop


def require_owner(user: User) -> None:
    if user.role != "owner":
        raise AppError("Only the owner can do that", 403)
