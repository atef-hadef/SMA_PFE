import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    encoded_digest = _base64url_encode(digest)
    return (
        f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}"
        f"${salt}${encoded_digest}"
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False

    try:
        algorithm, iterations, salt, encoded_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PASSWORD_HASH_ALGORITHM:
        return False

    try:
        iteration_count = int(iterations)
        expected_digest = _base64url_decode(encoded_digest)
    except (TypeError, ValueError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iteration_count,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    signing_input = (
        f"{_base64url_json(header)}.{_base64url_json(payload)}"
    )
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token format.") from exc

    signing_input = f"{header_segment}.{payload_segment}"
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid token signature.")

    try:
        header = json.loads(_base64url_decode(header_segment))
        payload = json.loads(_base64url_decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Invalid token payload.") from exc

    if header.get("alg") != settings.JWT_ALGORITHM:
        raise ValueError("Unsupported token algorithm.")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise ValueError("Token expiration is missing.")

    if datetime.now(timezone.utc).timestamp() >= expires_at:
        raise ValueError("Token has expired.")

    return payload


def _base64url_json(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
        "utf-8",
    )
    return _base64url_encode(serialized)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _sign(signing_input: str) -> str:
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)
