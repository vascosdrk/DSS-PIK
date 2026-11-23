"""
Authentication & Session Management Module for DSS-PIK Backend
Climate Early Warning System (CEWS) BMKG Kepulauan Riau
"""

import os
import time
import json
import hmac
import hashlib
import base64
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import Request, HTTPException, status
import bcrypt

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DSS_PIK_USERNAME = os.environ.get("DSS_PIK_USERNAME", "klimatkepri")
DSS_PIK_PASSWORD_HASH = os.environ.get("DSS_PIK_PASSWORD_HASH", "")
DSS_PIK_SESSION_SECRET = os.environ.get("DSS_PIK_SESSION_SECRET", "dss_pik_secret_fallback_key")
SESSION_COOKIE_NAME = "dss_pik_session"
SESSION_DURATION_SECONDS = 12 * 3600  # 12 hours


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash in constant time."""
    if not hashed_password or not plain_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        print(f"[AUTH ERROR] Password verification exception: {e}")
        return False


def authenticate_user(username_in: str, password_in: str) -> bool:
    """Validate user credentials against environment configuration."""
    if not username_in or not password_in:
        return False
    # Username check (case-insensitive for operator friendliness)
    if username_in.strip().lower() != DSS_PIK_USERNAME.strip().lower():
        return False
    return verify_password(password_in, DSS_PIK_PASSWORD_HASH)


def create_session_token(username: str, expires_in: int = SESSION_DURATION_SECONDS) -> str:
    """
    Generate a cryptographically signed session token.
    Format: <base64_payload>.<hmac_signature_hex>
    """
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + expires_in,
        "iss": "DSS-PIK-BMKG",
        "jti": uuid.uuid4().hex,
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    sig = hmac.new(
        DSS_PIK_SESSION_SECRET.encode('utf-8'),
        b64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return f"{b64_payload}.{sig}"


def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify signature and expiration of a session token.
    Returns decoded payload if valid, None otherwise.
    """
    if not token or "." not in token:
        return None
    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None
        b64_payload, signature = parts[0], parts[1]

        # Verify HMAC signature in constant time
        expected_sig = hmac.new(
            DSS_PIK_SESSION_SECRET.encode('utf-8'),
            b64_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Decode base64 payload (add padding if necessary)
        rem = len(b64_payload) % 4
        padded_b64 = b64_payload + ("=" * ((4 - rem) % 4))
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))

        # Check expiration
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return None

        return payload
    except Exception:
        return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract session token from cookie or Authorization Bearer header."""
    # 1. Cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token

    # 2. Authorization Header (Bearer token fallback)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None


def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency to protect endpoints. Raises 401 if unauthenticated."""
    token = extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi diperlukan. Silakan login terlebih dahulu.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_session_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak valid atau telah kedaluwarsa. Silakan login kembali.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "username": payload["sub"],
        "authenticated": True,
        "issued_at": payload.get("iat"),
        "expires_at": payload.get("exp")
    }
