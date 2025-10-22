import sys
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if "cryptography" not in sys.modules:
    cryptography_module = types.ModuleType("cryptography")
    hazmat_module = types.ModuleType("cryptography.hazmat")
    primitives_module = types.ModuleType("cryptography.hazmat.primitives")
    ciphers_module = types.ModuleType("cryptography.hazmat.primitives.ciphers")
    aead_module = types.ModuleType("cryptography.hazmat.primitives.ciphers.aead")

    class DummyAESGCM:
        def __init__(self, *_, **__):
            pass

        def encrypt(self, _nonce, data, _aad):
            return data.encode("utf-8") if isinstance(data, str) else data

        def decrypt(self, _nonce, data, _aad):
            return data.decode("utf-8") if isinstance(data, bytes) else data

    aead_module.AESGCM = DummyAESGCM

    hashes_module = types.ModuleType("cryptography.hazmat.primitives.hashes")

    class DummySHA256:
        digest_size = 32

        def __init__(self):
            pass

    hashes_module.SHA256 = DummySHA256

    pbkdf2_module = types.ModuleType("cryptography.hazmat.primitives.kdf.pbkdf2")

    class DummyPBKDF2HMAC:
        def __init__(self, *_, **__):
            pass

        def derive(self, _data):
            return b"0" * 32

    pbkdf2_module.PBKDF2HMAC = DummyPBKDF2HMAC

    kdf_module = types.ModuleType("cryptography.hazmat.primitives.kdf")
    kdf_module.pbkdf2 = pbkdf2_module

    primitives_module.ciphers = ciphers_module
    primitives_module.hashes = hashes_module
    primitives_module.kdf = kdf_module

    ciphers_module.aead = aead_module

    cryptography_module.hazmat = hazmat_module
    hazmat_module.primitives = primitives_module

    sys.modules["cryptography"] = cryptography_module
    sys.modules["cryptography.hazmat"] = hazmat_module
    sys.modules["cryptography.hazmat.primitives"] = primitives_module
    sys.modules["cryptography.hazmat.primitives.ciphers"] = ciphers_module
    sys.modules["cryptography.hazmat.primitives.ciphers.aead"] = aead_module
    sys.modules["cryptography.hazmat.primitives.hashes"] = hashes_module
    sys.modules["cryptography.hazmat.primitives.kdf"] = kdf_module
    sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = pbkdf2_module

from data.security.oauth_manager import OAuthManager


def test_store_token_preserves_refresh_token_and_metadata(tmp_path):
    class DummySecurityManager:
        def encrypt_dict(self, data):
            return data

        def decrypt_dict(self, data):
            return data

    tokens_dir = tmp_path / "tokens"

    oauth_manager = OAuthManager(DummySecurityManager(), config_dir=str(tokens_dir))

    provider = "test-provider"

    oauth_manager.store_token(
        provider=provider,
        access_token="initial-access",
        refresh_token="initial-refresh",
        expires_in=3600,
        token_type="Custom",
        scope="initial-scope",
        extra_field="extra-value",
    )

    initial_token = oauth_manager.get_token(provider)
    assert initial_token["refresh_token"] == "initial-refresh"
    assert initial_token["scope"] == "initial-scope"
    assert initial_token["token_type"] == "Custom"
    assert initial_token["extra_field"] == "extra-value"

    first_stored_at = initial_token["stored_at"]
    first_expires_at = initial_token["expires_at"]

    # Store updated token without refresh token or metadata overrides
    oauth_manager.store_token(
        provider=provider,
        access_token="updated-access",
        refresh_token=None,
        expires_in=1800,
        token_type=None,
        scope=None,
    )

    updated_token = oauth_manager.get_token(provider)

    assert updated_token["access_token"] == "updated-access"
    assert updated_token["refresh_token"] == "initial-refresh"
    assert updated_token["scope"] == "initial-scope"
    assert updated_token["token_type"] == "Custom"
    assert updated_token["extra_field"] == "extra-value"
    assert updated_token["expires_in"] == 1800
    assert updated_token["expires_at"] != first_expires_at
    assert updated_token["stored_at"] != first_stored_at
