import pytest
from cryptography.fernet import InvalidToken
from services.crypto_service import CryptoService


def test_crypto_round_trip():
    service = CryptoService(master_key="dGVzdF9tYXN0ZXJfa2V5XzMyX2J5dGVzX2xvbmdfMTIzNA==")
    salt = service.generate_salt()
    plaintext = "super_secret_telethon_session_string_1234567890"

    encrypted = service.encrypt_string(plaintext, salt)
    assert encrypted != plaintext
    assert len(encrypted) > len(plaintext)

    decrypted = service.decrypt_string(encrypted, salt)
    assert decrypted == plaintext


def test_crypto_user_isolation():
    service = CryptoService(master_key="dGVzdF9tYXN0ZXJfa2V5XzMyX2J5dGVzX2xvbmdfMTIzNA==")
    salt_user_a = service.generate_salt()
    salt_user_b = service.generate_salt()

    plaintext = "session_for_user_a"
    encrypted = service.encrypt_string(plaintext, salt_user_a)

    # Decrypting with user B's salt must fail
    with pytest.raises(InvalidToken):
        service.decrypt_string(encrypted, salt_user_b)


def test_crypto_file_round_trip(tmp_path):
    service = CryptoService()
    salt = service.generate_salt()

    src_file = tmp_path / "original.session"
    enc_file = tmp_path / "session.enc"
    dec_file = tmp_path / "restored.session"

    content = b"Binary SQLite database data for telethon session \x00\x01\x02\xFF"
    src_file.write_bytes(content)

    service.encrypt_file(src_file, enc_file, salt)
    assert enc_file.exists()
    assert enc_file.read_bytes() != content

    service.decrypt_file(enc_file, dec_file, salt)
    assert dec_file.read_bytes() == content
