from types import SimpleNamespace

from app.core import secrets


def test_keychain_write_uses_security_cli(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(secrets.sys, "platform", "darwin")
    monkeypatch.setattr(secrets.subprocess, "run", fake_run)
    store = secrets.MacOSKeychainSecretStore(
        service="test.service",
        account="test-user",
    )

    store.write("secret-value")

    assert calls == [
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            "test-user",
            "-s",
            "test.service",
            "-w",
            "secret-value",
        ]
    ]


def test_keychain_read_returns_empty_when_item_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(secrets.sys, "platform", "darwin")
    monkeypatch.setattr(
        secrets.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=44,
            stdout="",
            stderr="not found",
        ),
    )

    assert secrets.MacOSKeychainSecretStore().read() == ""
