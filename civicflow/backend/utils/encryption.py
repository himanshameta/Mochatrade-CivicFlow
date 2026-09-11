"""
CivicFlow — AES-256-GCM Field Encryption
==========================================
User-specific encryption keys derived via PBKDF2HMAC (SHA-256).
Keys are NEVER stored — re-derived from (user_id + APP_SALT) on every call.

Usage:
    from utils.encryption import encrypt_field, decrypt_field

    encrypted = encrypt_field("Rahul Kumar", user_id="abc-123")
    plain     = decrypt_field(encrypted, user_id="abc-123")

Fields listed in ENCRYPTED_PROFILE_FIELDS are automatically encrypted
when saving a UserProfileData document and decrypted on retrieval.
"""
import os
import base64
from typing import Optional

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print(
        "[Encryption] [WARNING] cryptography package not installed — "
        "field encryption disabled. Run: pip install cryptography"
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# App-level salt — read from .env.
# IMPORTANT: Never change this after first deployment or all encrypted data
# becomes unrecoverable. Store safely in your secrets manager.
_APP_SALT: bytes = os.getenv(
    "ENCRYPTION_SALT", "civicflow-salt-change-before-production"
).encode("utf-8")

_KDF_ITERATIONS = 100_000  # NIST recommended minimum for PBKDF2-SHA256
_KEY_LENGTH = 32            # 256 bits → AES-256

# Which fields in basic_info / contact / identity are encrypted at rest
ENCRYPTED_BASIC_FIELDS = ["full_name", "dob", "address", "phone"]
ENCRYPTED_CONTACT_FIELDS = ["phone"]
ENCRYPTED_IDENTITY_FIELDS = ["pan_number"]


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def generate_user_key(user_id: str) -> bytes:
    """
    Derive a 256-bit AES key unique to this user.
    Key = PBKDF2HMAC(SHA-256, password=user_id, salt=APP_SALT, iter=100k)

    The key is deterministic and never stored — re-derived on every call.
    Each user has a unique key so a single DB breach cannot decrypt all users.

    Raises RuntimeError if the cryptography package is not installed.
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError(
            "cryptography package not installed. Run: pip install cryptography"
        )

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=_APP_SALT,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(user_id.encode("utf-8"))


# ---------------------------------------------------------------------------
# Encrypt / decrypt
# ---------------------------------------------------------------------------

def encrypt_field(value: str, user_id: str) -> str:
    """
    Encrypt a string using AES-256-GCM with a user-specific key.

    Returns a string in the format:  "<nonce_b64>:<ciphertext_b64>"
    Nonce is 12 bytes (96-bit), randomly generated per call.

    If the cryptography package is unavailable (dev mode), stores a
    base64-prefixed plaintext so decryption still works deterministically.

    Args:
        value:    Plaintext string to encrypt (empty string returned as-is)
        user_id:  UUID of the owning user (drives key derivation)

    Returns:
        Encrypted string or original value if empty
    """
    if not value:
        return value

    if not CRYPTO_AVAILABLE:
        # Dev-mode passthrough: mark as plaintext so decrypt works
        return "plain:" + base64.b64encode(value.encode("utf-8")).decode("utf-8")

    key = generate_user_key(user_id)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit random nonce — unique per encryption
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)

    nonce_b64 = base64.b64encode(nonce).decode("utf-8")
    cipher_b64 = base64.b64encode(ciphertext).decode("utf-8")
    return f"{nonce_b64}:{cipher_b64}"


def decrypt_field(encrypted: str, user_id: str) -> str:
    """
    Decrypt a field encrypted with encrypt_field().

    Args:
        encrypted: Output of encrypt_field(), or empty string
        user_id:   UUID of the owning user (must match the one used to encrypt)

    Returns:
        Plaintext string, or empty string if decryption fails
    """
    if not encrypted:
        return encrypted

    # Handle dev-mode passthrough values
    if encrypted.startswith("plain:"):
        try:
            return base64.b64decode(encrypted[6:]).decode("utf-8")
        except Exception:
            return ""

    if not CRYPTO_AVAILABLE:
        # Cannot decrypt — return raw (will look garbled but won't crash)
        return encrypted

    try:
        parts = encrypted.split(":", 1)
        if len(parts) != 2:
            return ""

        nonce = base64.b64decode(parts[0])
        ciphertext = base64.b64decode(parts[1])

        key = generate_user_key(user_id)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    except Exception as e:
        print(f"[Encryption] [WARNING] Decryption failed for user {user_id[:8]}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Dict-level helpers (for encrypting nested profile sub-dicts)
# ---------------------------------------------------------------------------

def encrypt_dict_fields(data: dict, user_id: str, fields: list) -> dict:
    """
    Return a copy of `data` with the specified `fields` encrypted.
    Fields not in `data` or with falsy values are left unchanged.
    """
    result = dict(data)
    for field in fields:
        if result.get(field):
            result[field] = encrypt_field(str(result[field]), user_id)
    return result


def decrypt_dict_fields(data: dict, user_id: str, fields: list) -> dict:
    """
    Return a copy of `data` with the specified `fields` decrypted.
    Inverse of encrypt_dict_fields.
    """
    result = dict(data)
    for field in fields:
        if result.get(field):
            result[field] = decrypt_field(str(result[field]), user_id)
    return result


# ---------------------------------------------------------------------------
# Profile-level convenience wrappers
# ---------------------------------------------------------------------------

def encrypt_profile(profile_dict: dict, user_id: str) -> dict:
    """
    Encrypt all sensitive fields in a UserProfileData dict before saving to MongoDB.
    Operates on basic_info, contact, and identity sub-dicts.
    """
    result = dict(profile_dict)

    if "basic_info" in result and result["basic_info"]:
        result["basic_info"] = encrypt_dict_fields(
            result["basic_info"], user_id, ENCRYPTED_BASIC_FIELDS
        )

    if "contact" in result and result["contact"]:
        result["contact"] = encrypt_dict_fields(
            result["contact"], user_id, ENCRYPTED_CONTACT_FIELDS
        )

    if "identity" in result and result["identity"]:
        result["identity"] = encrypt_dict_fields(
            result["identity"], user_id, ENCRYPTED_IDENTITY_FIELDS
        )

    return result


def decrypt_profile(profile_dict: dict, user_id: str) -> dict:
    """
    Decrypt all sensitive fields in a UserProfileData dict after loading from MongoDB.
    """
    result = dict(profile_dict)

    if "basic_info" in result and result["basic_info"]:
        result["basic_info"] = decrypt_dict_fields(
            result["basic_info"], user_id, ENCRYPTED_BASIC_FIELDS
        )

    if "contact" in result and result["contact"]:
        result["contact"] = decrypt_dict_fields(
            result["contact"], user_id, ENCRYPTED_CONTACT_FIELDS
        )

    if "identity" in result and result["identity"]:
        result["identity"] = decrypt_dict_fields(
            result["identity"], user_id, ENCRYPTED_IDENTITY_FIELDS
        )

    return result
