import pytest
from db.crypto import encrypt_secret, decrypt_secret, mask_secret


def test_encrypt_decrypt_roundtrip():
    plain = "super-secret-token"
    cipher = encrypt_secret(plain)

    assert cipher != plain
    assert decrypt_secret(cipher) == plain


def test_encrypt_is_not_deterministic():
    # Fernet 每次加密都會帶入新的隨機值，同樣明文兩次加密結果應不同
    plain = "same-input"
    assert encrypt_secret(plain) != encrypt_secret(plain)


def test_decrypt_invalid_token_raises():
    with pytest.raises(ValueError):
        decrypt_secret("not-a-real-fernet-token")


def test_mask_secret_keeps_last_four_chars_only():
    original = "ghp_1234567890abcdef"
    masked = mask_secret(original)

    assert masked.endswith("cdef")
    assert len(masked) == len(original)
    assert "1234567890abcdef" not in masked


def test_mask_secret_short_string_is_fully_masked():
    assert mask_secret("abc") == "***"


def test_missing_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        encrypt_secret("x")
