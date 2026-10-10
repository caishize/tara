"""
Encryption service implementation using AES-256-GCM.
"""
import base64
import hashlib
from uuid import UUID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

from ..interfaces.encryption import IEncryptionProvider
from ...config.settings import settings


class EncryptionService(IEncryptionProvider):
    """
    Field-level encryption service using AES-256-GCM.

    Each family gets a derived key from master key + family_id salt.
    """

    def __init__(self):
        self.master_key = settings.encryption_master_key.encode()
        if len(self.master_key) < 32:
            # Pad to 32 bytes if needed
            self.master_key = self.master_key.ljust(32, b'0')

    async def get_family_key(self, family_id: UUID) -> bytes:
        """Derive family-specific key using HKDF."""
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=str(family_id).encode(),
            info=b'family-encryption-key',
            backend=default_backend()
        )
        return kdf.derive(self.master_key)

    async def encrypt(self, plaintext: str, family_id: UUID) -> str:
        """
        Encrypt plaintext with AES-256-GCM.

        Returns: base64(nonce + ciphertext + tag)
        """
        if not plaintext:
            return ""

        key = await self.get_family_key(family_id)
        aesgcm = AESGCM(key)

        # Generate random 12-byte nonce
        import os
        nonce = os.urandom(12)

        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext (tag is included in ciphertext by AESGCM)
        combined = nonce + ciphertext

        # Return base64-encoded
        return base64.b64encode(combined).decode()

    async def decrypt(self, ciphertext: str, family_id: UUID) -> str:
        """
        Decrypt ciphertext with AES-256-GCM.

        Expects: base64(nonce + ciphertext + tag)
        """
        if not ciphertext:
            return ""

        try:
            key = await self.get_family_key(family_id)
            aesgcm = AESGCM(key)

            # Decode base64
            combined = base64.b64decode(ciphertext)

            # Split nonce and ciphertext
            nonce = combined[:12]
            encrypted_data = combined[12:]

            # Decrypt
            plaintext = aesgcm.decrypt(nonce, encrypted_data, None)

            return plaintext.decode()

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")


# Global instance
encryption_service = EncryptionService()
