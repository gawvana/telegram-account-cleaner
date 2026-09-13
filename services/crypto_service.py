import base64
import os
from pathlib import Path
from typing import Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import settings
from utils.logger import logger


class CryptoService:
    """Manages at-rest encryption and decryption of Telethon sessions and sensitive data."""

    def __init__(self, master_key: str = ""):
        self._master_key_str = master_key or settings.ENCRYPTION_MASTER_KEY
        if not self._master_key_str:
            # Generate deterministic fallback for dev/testing if not set, with prominent warning
            logger.warning(
                "ENCRYPTION_MASTER_KEY is not set in environment! "
                "Generating a temporary session key for development."
            )
            self._master_key_bytes = Fernet.generate_key()
        else:
            try:
                # Validate if it's already a valid Fernet key
                Fernet(self._master_key_str.encode("utf-8"))
                self._master_key_bytes = self._master_key_str.encode("utf-8")
            except Exception:
                # If raw passphrase, derive 32-byte key
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"antigravity_salt_master",
                    iterations=100_000,
                )
                self._master_key_bytes = base64.urlsafe_b64encode(
                    kdf.derive(self._master_key_str.encode("utf-8"))
                )

    @staticmethod
    def generate_salt() -> str:
        """Generates a secure cryptographically random hex salt per user."""
        return os.urandom(16).hex()

    def get_user_fernet(self, user_salt: str) -> Fernet:
        """Derives a distinct per-user Fernet key combining master key and user salt."""
        salt_bytes = bytes.fromhex(user_salt) if len(user_salt) == 32 else user_salt.encode("utf-8")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=100_000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(self._master_key_bytes))
        return Fernet(derived_key)

    def encrypt_bytes(self, data: bytes, user_salt: str) -> bytes:
        """Encrypts arbitrary bytes using user-derived Fernet."""
        fernet = self.get_user_fernet(user_salt)
        return fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes, user_salt: str) -> bytes:
        """Decrypts bytes using user-derived Fernet."""
        fernet = self.get_user_fernet(user_salt)
        return fernet.decrypt(encrypted_data)

    def encrypt_string(self, text: str, user_salt: str) -> str:
        """Encrypts UTF-8 string to base64 encrypted string."""
        encrypted = self.encrypt_bytes(text.encode("utf-8"), user_salt)
        return encrypted.decode("utf-8")

    def decrypt_string(self, encrypted_text: str, user_salt: str) -> str:
        """Decrypts encrypted string back to UTF-8 plaintext."""
        decrypted = self.decrypt_bytes(encrypted_text.encode("utf-8"), user_salt)
        return decrypted.decode("utf-8")

    def encrypt_file(self, source_path: Union[str, Path], dest_path: Union[str, Path], user_salt: str) -> None:
        """Reads file from source_path, encrypts contents, and writes to dest_path."""
        src = Path(source_path)
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw_data = src.read_bytes()
        encrypted_data = self.encrypt_bytes(raw_data, user_salt)
        dest.write_bytes(encrypted_data)
        # Set file permissions to 600 (read/write only by owner) on Unix if available
        try:
            os.chmod(dest, 0o600)
        except Exception:
            pass

    def decrypt_file(self, source_path: Union[str, Path], dest_path: Union[str, Path], user_salt: str) -> None:
        """Reads encrypted file from source_path, decrypts contents, and writes to dest_path."""
        src = Path(source_path)
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        encrypted_data = src.read_bytes()
        decrypted_data = self.decrypt_bytes(encrypted_data, user_salt)
        dest.write_bytes(decrypted_data)
        try:
            os.chmod(dest, 0o600)
        except Exception:
            pass

    def decrypt_file_to_bytes(self, source_path: Union[str, Path], user_salt: str) -> bytes:
        """Reads encrypted file and returns decrypted bytes in-memory."""
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Encrypted session file not found: {source_path}")
        encrypted_data = src.read_bytes()
        return self.decrypt_bytes(encrypted_data, user_salt)


crypto_service = CryptoService()
