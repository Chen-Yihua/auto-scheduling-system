import pytest
from db.crypto import encrypt_secret, decrypt_secret, mask_secret


def test_encrypt_decrypt_roundtrip():
    """加密後再解密要還原成原本的明文，且密文不能等於明文。"""
    plain = "super-secret-token"
    cipher = encrypt_secret(plain)

    assert cipher != plain
    assert decrypt_secret(cipher) == plain


def test_encrypt_is_not_deterministic():
    """同樣的明文兩次加密結果要不同（Fernet 每次都帶新的隨機值），避免有人靠比對密文猜出內容。"""
    plain = "same-input"
    assert encrypt_secret(plain) != encrypt_secret(plain)


def test_decrypt_invalid_token_raises():
    """解密不是合法密文的字串 → 丟 ValueError。"""
    with pytest.raises(ValueError):
        decrypt_secret("not-a-real-fernet-token")


def test_mask_secret_keeps_last_four_chars_only():
    """遮罩只保留最後 4 個字元，長度不變，前面的內容不能外洩。"""
    original = "ghp_1234567890abcdef"
    masked = mask_secret(original)

    assert masked.endswith("cdef")
    assert len(masked) == len(original)
    assert "1234567890abcdef" not in masked


def test_mask_secret_short_string_is_fully_masked():
    """太短的字串（3 個字元）要全部遮住，不留任何字元。"""
    assert mask_secret("abc") == "***"


def test_missing_key_raises_runtime_error(monkeypatch):
    """沒設定 SECRET_ENCRYPTION_KEY 時要丟 RuntimeError，不能悄悄用預設金鑰加密。"""
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        encrypt_secret("x")
