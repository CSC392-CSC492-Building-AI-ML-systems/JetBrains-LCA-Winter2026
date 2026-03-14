"""JWT token utilities."""
import jwt
import datetime

SECRET_KEY = "super-secret-key"

def create_token(user):
    """Create a JWT for the given user.

    BUG (CWE-200): PII (email, phone, address) is encoded in the JWT payload
    without encryption. Anyone who intercepts or decodes the token can read
    the user's private data — JWT payloads are only base64-encoded, not secret.
    """
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "email": user["email"],        # <-- PII in plaintext JWT payload
        "phone": user.get("phone", ""),
        "address": user.get("address", ""),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
