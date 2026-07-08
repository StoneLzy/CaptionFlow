import getpass
import subprocess
import sys
from dataclasses import dataclass

from app.core.paths import BUNDLE_ID

PROVIDER_API_KEY_SERVICE = f"{BUNDLE_ID}.provider-api-key"


@dataclass(frozen=True)
class MacOSKeychainSecretStore:
    service: str = PROVIDER_API_KEY_SERVICE
    account: str = getpass.getuser()

    @property
    def supported(self) -> bool:
        return sys.platform == "darwin"

    def read(self) -> str:
        if not self.supported:
            return ""
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                self.account,
                "-s",
                self.service,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def write(self, value: str) -> None:
        if not self.supported:
            raise RuntimeError("Secure API key storage is only available on macOS")
        secret = value.strip()
        if not secret:
            raise ValueError("API key cannot be empty")
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-a",
                self.account,
                "-s",
                self.service,
                "-w",
                secret,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown Keychain error"
            raise RuntimeError(f"Failed to store API key in Keychain: {detail}")

    def delete(self) -> None:
        if not self.supported:
            return
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                self.account,
                "-s",
                self.service,
            ],
            capture_output=True,
            text=True,
            check=False,
        )


def resolve_provider_api_key(environment_value: str) -> str:
    return MacOSKeychainSecretStore().read() or environment_value
