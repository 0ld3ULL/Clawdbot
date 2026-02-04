"""
Encrypted credential storage for the agent system.

Credentials are AES-encrypted at rest using a key stored ONLY in an
environment variable (never on disk). This prevents credential exposure
if the data directory is compromised.

Usage:
    store = CredentialStore()
    store.set("twitter_api_key", "sk-...")
    key = store.get("twitter_api_key")
"""

import os
import json
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken


class CredentialStore:

    def __init__(self, store_path: str = "data/credentials.enc"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        key = os.environ.get("AGENT_CRED_KEY")
        if not key:
            raise ValueError(
                "AGENT_CRED_KEY environment variable required. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            self.cipher = Fernet(key.encode())
        except Exception as e:
            raise ValueError(f"Invalid AGENT_CRED_KEY: {e}")

    def get(self, name: str) -> str:
        """Get a credential by name. Returns empty string if not found."""
        store = self._load()
        return store.get(name, "")

    def set(self, name: str, value: str):
        """Set a credential (encrypts and saves immediately)."""
        store = self._load()
        store[name] = value
        self._save(store)

    def delete(self, name: str):
        """Delete a credential."""
        store = self._load()
        store.pop(name, None)
        self._save(store)

    def list_keys(self) -> list[str]:
        """List all stored credential names (not values)."""
        store = self._load()
        return list(store.keys())

    def has(self, name: str) -> bool:
        """Check if a credential exists."""
        store = self._load()
        return name in store

    def _load(self) -> dict:
        if not self.store_path.exists():
            return {}
        try:
            encrypted = self.store_path.read_bytes()
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted)
        except InvalidToken:
            raise ValueError(
                "Failed to decrypt credentials. "
                "AGENT_CRED_KEY may have changed since credentials were stored."
            )

    def _save(self, store: dict):
        encrypted = self.cipher.encrypt(json.dumps(store).encode())
        self.store_path.write_bytes(encrypted)


def generate_key():
    """Generate a new encryption key. Run this once during setup."""
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    print("New encryption key:", generate_key())
    print("Set this as AGENT_CRED_KEY in your .env file.")
