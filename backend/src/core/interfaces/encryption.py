"""
IEncryptionProvider interface.
"""
from abc import ABC, abstractmethod
from uuid import UUID


class EncryptionError(Exception):
    """Exception raised by encryption service."""
    pass


class IEncryptionProvider(ABC):
    """Interface for encryption provider."""

    @abstractmethod
    async def get_family_key(self, family_id: UUID) -> bytes:
        """
        Get or derive encryption key for a specific family.

        Args:
            family_id: Family UUID

        Returns:
            32-byte encryption key
        """
        pass

    @abstractmethod
    async def encrypt(self, plaintext: str, family_id: UUID) -> str:
        """
        Encrypt plaintext using family-specific key.

        Args:
            plaintext: Data to encrypt
            family_id: Family UUID

        Returns:
            Base64-encoded ciphertext
        """
        pass

    @abstractmethod
    async def decrypt(self, ciphertext: str, family_id: UUID) -> str:
        """
        Decrypt ciphertext using family-specific key.

        Args:
            ciphertext: Base64-encoded encrypted data
            family_id: Family UUID

        Returns:
            Decrypted plaintext
        """
        pass
