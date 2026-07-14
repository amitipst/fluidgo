import secrets
import string
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── Password policy ─────────────────────────────────────────────────────────
# NIST 800-63B aligned: length matters far more than forced character
# classes, which push people toward predictable patterns like "Fluid@123"
# that satisfy a regex but not an attacker. We enforce a longer minimum
# instead, block the passwords that show up in literally every breach list
# and every credential-stuffing attempt, and block passwords built from the
# user's own name/email (the most common thing people fall back to when a
# random string feels annoying to remember).
PASSWORD_MIN_LENGTH = 10

_COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789",
    "1234567890", "qwerty123", "letmein123", "welcome123", "admin123",
    "changeme", "changeme123", "iloveyou", "monkey123", "football123",
    "fluidgo", "fluidgo123", "fluidpro", "fluidpro123", "wepsol123",
    "wepsolutions", "abc123456", "sunshine1", "princess1", "dragon123",
}

def validate_password_policy(password: str, name: str = "", email: str = "") -> str | None:
    """Returns an error message if the password fails policy, else None.
    Deliberately does NOT require uppercase/number/symbol classes — see note
    above. Called from both the self-service change-password endpoint and
    the reset-password (email-link) endpoint, so the two paths can't drift."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if password.lower() in _COMMON_PASSWORDS:
        return "This password is too common. Please choose something more unique."
    local_part = (email.split("@")[0] if email else "").lower()
    first_name = (name.split()[0] if name else "").lower()
    pw_lower = password.lower()
    if local_part and len(local_part) >= 4 and local_part in pw_lower:
        return "Password cannot contain your email address."
    if first_name and len(first_name) >= 4 and first_name in pw_lower:
        return "Password cannot contain your name."
    return None

def generate_temp_password() -> str:
    """Cryptographically random temp password for admin-initiated resets —
    the admin never chooses (and can't reuse) a weak/predictable one. Mixed
    alnum, no ambiguous-looking chars (0/O, 1/l/I) so it's easy to read back
    over a phone call or WhatsApp message, 14 chars => well clear of
    PASSWORD_MIN_LENGTH with margin for the policy check above."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(14))

def create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_access_token(user_id: str, role: str) -> str:
    return create_token(
        {"sub": user_id, "role": role, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

def create_refresh_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
