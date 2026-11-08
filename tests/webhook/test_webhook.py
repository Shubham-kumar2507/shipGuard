import hashlib
import hmac
import json

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from shipguard.webhook import (
    GitHubAppClient,
    WebhookSettings,
    _safe_cli_environment,
    create_app,
)


def _settings(secret: str = "hook-" + "secret") -> WebhookSettings:
    return WebhookSettings(
        webhook_secret=secret,
        app_id="12345",
        app_private_key="unused-in-webhook-tests",
    )


def _payload() -> dict[str, object]:
    sha = "a" * 40
    return {
        "action": "opened",
        "installation": {"id": 42},
        "repository": {"full_name": "owner/repository"},
        "pull_request": {
            "number": 7,
            "base": {"sha": "b" * 40},
            "head": {"sha": sha},
        },
    }


def _signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_verifies_signature_and_schedules_pull_request() -> None:
    settings = _settings()
    received = []
    app = create_app(settings, processor=lambda *args: received.append(args))
    body = json.dumps(_payload()).encode()

    response = TestClient(app).post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": _signature(settings.webhook_secret, body),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-1",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert len(received) == 1
    assert received[0][0].pull_request.number == 7
    assert received[0][1] == "delivery-1"


def test_webhook_rejects_invalid_signature_before_parsing() -> None:
    received = []
    app = create_app(_settings(), processor=lambda *args: received.append(args))

    response = TestClient(app).post(
        "/webhook",
        content=b"not-json",
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "pull_request",
        },
    )

    assert response.status_code == 401
    assert received == []


def test_webhook_ignores_non_pull_request_events() -> None:
    settings = _settings()
    body = b"{}"
    app = create_app(settings)

    response = TestClient(app).post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": _signature(settings.webhook_secret, body),
            "X-GitHub-Event": "push",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}


def test_webhook_rejects_oversized_payload() -> None:
    app = create_app(_settings().model_copy(update={"max_payload_bytes": 1024}))

    response = TestClient(app).post(
        "/webhook",
        content=b"x" * 1025,
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
    )

    assert response.status_code == 413


def test_safe_cli_environment_does_not_inherit_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "runtime-" + "token")
    monkeypatch.setenv("SHIPGUARD_LLM_API_KEY", "runtime-" + "key")
    monkeypatch.setenv("SHIPGUARD_WEBHOOK_SECRET", "runtime-" + "secret")
    monkeypatch.setenv("PATH", "safe-path")

    environment = _safe_cli_environment()

    assert environment["PATH"] == "safe-path"
    assert "GITHUB_TOKEN" not in environment
    assert "SHIPGUARD_LLM_API_KEY" not in environment
    assert "SHIPGUARD_WEBHOOK_SECRET" not in environment


def test_app_jwt_is_signed_with_github_app_identity() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    settings = WebhookSettings(
        webhook_secret="hook-secret",
        app_id="12345",
        app_private_key=private_pem,
    )
    client = GitHubAppClient(settings, client=httpx.Client())

    token = client._create_app_jwt()
    claims = jwt.decode(
        token,
        private_key.public_key(),
        algorithms=["RS256"],
        options={"require": ["iat", "exp", "iss"]},
    )

    assert claims["iss"] == "12345"
    assert claims["exp"] - claims["iat"] == 600
    client.close()


@respx.mock
def test_app_client_exchanges_jwt_and_updates_check_run() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    settings = WebhookSettings(
        webhook_secret="hook-secret",
        app_id="12345",
        app_private_key=private_pem,
    )
    token_route = respx.post(
        "https://api.github.com/app/installations/42/access_tokens"
    ).mock(return_value=httpx.Response(201, json={"token": "installation-token"}))
    create_route = respx.post(
        "https://api.github.com/repos/owner/repository/check-runs"
    ).mock(return_value=httpx.Response(201, json={"id": 17}))
    update_route = respx.patch(
        "https://api.github.com/repos/owner/repository/check-runs/17"
    ).mock(return_value=httpx.Response(200, json={"id": 17}))
    client = GitHubAppClient(settings)

    token = client.create_installation_token(42)
    check_id = client.create_check_run(
        "owner/repository", "a" * 40, token, "delivery"
    )
    client.complete_check_run(
        "owner/repository",
        check_id,
        token,
        conclusion="success",
        title="Passed",
        summary="No findings",
        annotations=[],
    )

    assert token == "installation-token"
    assert check_id == 17
    assert token_route.called
    assert create_route.called
    assert update_route.called
    client.close()
