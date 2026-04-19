from __future__ import annotations

from typing import Optional

import keyring

KEYCHAIN_APP = "erasure"

SUPPORTED_SERVICES = frozenset({"simplelogin", "addy_io", "capsolver", "twilio"})


class SecretsManager:
    def get_token(self, service: str) -> Optional[str]:
        self._validate(service)
        return keyring.get_password(KEYCHAIN_APP, service)

    def set_token(self, service: str, token: str) -> None:
        self._validate(service)
        keyring.set_password(KEYCHAIN_APP, service, token)

    def delete_token(self, service: str) -> None:
        self._validate(service)
        keyring.delete_password(KEYCHAIN_APP, service)

    @staticmethod
    def _validate(service: str) -> None:
        if service not in SUPPORTED_SERVICES:
            raise ValueError(
                f"Unknown service {service!r}. Supported: {sorted(SUPPORTED_SERVICES)}"
            )
