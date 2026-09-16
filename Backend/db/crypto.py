# Backend/db/crypto.py
"""
用來加密/解密第三方帳密（GitHub apiKey、Jira apiKey、Moodle password）。
密文才會寫進 MongoDB；明文只在需要呼叫第三方 API 的當下於伺服器記憶體中短暫存在，
絕不回傳給前端。
"""
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
    """加密明文，回傳可存入 DB 的密文字串。"""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    """解密 DB 中的密文，取回原始明文（僅限伺服器內部呼叫第三方 API 時使用）。"""
    try:
        return _get_fernet().decrypt(cipher.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt secret: invalid token or wrong key")


def mask_secret(plain: str, visible: int = 4) -> str:
    """回傳遮罩後字串，只保留最後 N 碼，給前端顯示用，絕不含完整明文。"""
    if len(plain) <= visible:
        return "*" * len(plain)
    return "*" * (len(plain) - visible) + plain[-visible:]
