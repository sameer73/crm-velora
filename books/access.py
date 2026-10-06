import re
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from books.errors import AppError
from books.models import ApiToken, Profile, Shop


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


def needs_setup() -> bool:
    return not User.objects.exists()


def ensure_profile(user: User, name: str | None = None, role: str | None = None) -> Profile:
    display = " ".join(part for part in (user.first_name, user.last_name) if part).strip() or user.username
    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return Profile.objects.create(
            user=user,
            name=((name or display) or user.username)[:120],
            role=role or ("owner" if user.is_superuser else "staff"),
        )
    updates = []
    if name and profile.name != name:
        profile.name = name[:120]
        updates.append("name")
    if role and profile.role != role:
        profile.role = role
        updates.append("role")
    if updates:
        profile.save(update_fields=updates)
    return profile


def shops_for(user: User):
    profile = ensure_profile(user)
    if profile.is_owner:
        return Shop.objects.all()
    return profile.shops.all()


def require_shop(user: User, shop_id: int) -> Shop:
    shop = Shop.objects.filter(pk=shop_id).first()
    if shop is None:
        raise AppError("Shop not found", 404)
    profile = ensure_profile(user)
    if not profile.is_owner and not profile.shops.filter(pk=shop_id).exists():
        raise AppError("You cannot use this shop", 403)
    return shop


def require_owner(user: User) -> None:
    if not ensure_profile(user).is_owner:
        raise AppError("Only the owner can do that", 403)


def start_token(user: User) -> str:
    key = secrets.token_urlsafe(32)
    ApiToken.objects.create(key=key, user=user, expires_at=timezone.now() + timedelta(days=30))
    return key


def user_from_token(key: str | None) -> User | None:
    if not key:
        return None
    row = ApiToken.objects.select_related("user", "user__profile").filter(pk=key).first()
    if row is None:
        return None
    if row.expires_at < timezone.now():
        row.delete()
        return None
    return row.user


def end_token(key: str | None) -> None:
    if key:
        ApiToken.objects.filter(pk=key).delete()
