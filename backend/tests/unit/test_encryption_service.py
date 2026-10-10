"""
Unit tests for EncryptionService.
"""
import pytest
from uuid import uuid4

from src.core.auth.encryption_service import EncryptionService


@pytest.fixture
def encryption_service():
    """Encryption service fixture."""
    return EncryptionService()


@pytest.fixture
def family_id():
    """Test family ID."""
    return uuid4()


@pytest.mark.asyncio
async def test_encrypt_decrypt_roundtrip(encryption_service, family_id):
    """Test encrypt then decrypt returns original plaintext."""
    plaintext = "13812345678"

    ciphertext = await encryption_service.encrypt(plaintext, family_id)
    decrypted = await encryption_service.decrypt(ciphertext, family_id)

    assert decrypted == plaintext
    assert ciphertext != plaintext


@pytest.mark.asyncio
async def test_different_family_keys(encryption_service):
    """Test same plaintext encrypted with different family_ids produces different ciphertexts."""
    plaintext = "test@example.com"
    family1 = uuid4()
    family2 = uuid4()

    ciphertext1 = await encryption_service.encrypt(plaintext, family1)
    ciphertext2 = await encryption_service.encrypt(plaintext, family2)

    assert ciphertext1 != ciphertext2


@pytest.mark.asyncio
async def test_decrypt_with_wrong_family_id(encryption_service):
    """Test decryption fails with wrong family_id."""
    plaintext = "secret"
    correct_family = uuid4()
    wrong_family = uuid4()

    ciphertext = await encryption_service.encrypt(plaintext, correct_family)

    with pytest.raises(ValueError):
        await encryption_service.decrypt(ciphertext, wrong_family)


@pytest.mark.asyncio
async def test_encrypt_empty_string(encryption_service, family_id):
    """Test handles empty string."""
    result = await encryption_service.encrypt("", family_id)
    assert result == ""


@pytest.mark.asyncio
async def test_decrypt_invalid_ciphertext(encryption_service, family_id):
    """Test raises error for malformed ciphertext."""
    with pytest.raises(ValueError):
        await encryption_service.decrypt("invalid_base64", family_id)
