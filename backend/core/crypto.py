"""加解密第三方憑證。DB 只存密文，明文只在呼叫第三方 API 時使用，不回傳給前端。"""
import os
from cryptography.fernet import Fernet, InvalidToken

_KEY_ENV = "SECRET_ENCRYPTION_KEY"


def _get_fernet() -> Fernet:
    key = os.getenv(_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"Missing {_KEY_ENV} environment variable. "
            "Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_secret(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    try:
        return _get_fernet().decrypt(cipher.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt secret: invalid token or wrong key")


def mask_secret(plain: str, visible: int = 4) -> str:
    """只保留最後 visible 碼，給前端顯示用。"""
    if len(plain) <= visible:
        return "*" * len(plain)
    return "*" * (len(plain) - visible) + plain[-visible:]
