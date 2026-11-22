import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator


sys.path.append(str(Path(__file__).parent.parent / "src"))

import whatsapp_server


WEBHOOK_URL = "http://testserver/whatsapp/webhook"
TWILIO_AUTH_TOKEN = "test-twilio-auth-token"


class StubAssistant:
    def __init__(self, response="Respuesta de prueba", error=None):
        self.response = response
        self.error = error
        self.received = []

    def handle_whatsapp_message(self, from_number, message_body):
        self.received.append((from_number, message_body))
        if self.error:
            raise self.error
        return self.response

    def send_whatsapp_message(self, to_number, message):  # noqa: ARG002 - stub of the real assistant interface
        return {"success": True, "sid": "SM123", "status": "queued"}


def sign(params):
    return RequestValidator(TWILIO_AUTH_TOKEN).compute_signature(WEBHOOK_URL, params)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    monkeypatch.delenv("SEND_MESSAGE_API_KEY", raising=False)
    app = whatsapp_server.create_fastapi_app()
    return TestClient(app)


def install_assistant(monkeypatch, assistant):
    monkeypatch.setattr(whatsapp_server, "assistant", assistant)


class TestWebhookSignature:
    def test_rejects_unsigned_request(self, client, monkeypatch):
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/whatsapp/webhook",
            data={"From": "whatsapp:+15550001111", "Body": "hola"},
        )

        assert response.status_code == 403
        assert whatsapp_server.assistant.received == []

    def test_rejects_wrong_signature(self, client, monkeypatch):
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/whatsapp/webhook",
            data={"From": "whatsapp:+15550001111", "Body": "hola"},
            headers={"X-Twilio-Signature": "deadbeef"},
        )

        assert response.status_code == 403
        assert whatsapp_server.assistant.received == []

    def test_rejects_when_auth_token_unset(self, client, monkeypatch):
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/whatsapp/webhook",
            data={"From": "whatsapp:+15550001111", "Body": "hola"},
            headers={"X-Twilio-Signature": sign({"From": "whatsapp:+15550001111", "Body": "hola"})},
        )

        assert response.status_code == 403
        assert whatsapp_server.assistant.received == []


class TestWebhookHandling:
    def test_signed_request_returns_twiml_response(self, client, monkeypatch):
        stub = StubAssistant(response="BMW X5 disponible")
        install_assistant(monkeypatch, stub)

        params = {"From": "whatsapp:+15550001111", "Body": "busco un bmw"}
        response = client.post(
            "/whatsapp/webhook", data=params, headers={"X-Twilio-Signature": sign(params)}
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/xml")
        assert "BMW X5 disponible" in response.text
        assert stub.received == [("+15550001111", "busco un bmw")]

    def test_agent_failure_returns_generic_message_without_details(
        self, client, monkeypatch
    ):
        install_assistant(
            monkeypatch,
            StubAssistant(error=RuntimeError("postgresql://user:secret@host/db")),
        )

        params = {"From": "whatsapp:+15550001111", "Body": "hola"}
        response = client.post(
            "/whatsapp/webhook", data=params, headers={"X-Twilio-Signature": sign(params)}
        )

        assert response.status_code == 200
        assert whatsapp_server.GENERIC_ERROR_RESPONSE in response.text
        assert "secret" not in response.text
        assert "postgresql" not in response.text

    def test_webhook_verify_returns_plain_text_challenge(self, client):
        response = client.get("/whatsapp/webhook?hub.challenge=123456")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.text == "123456"


class TestSendMessageEndpoint:
    def test_disabled_without_api_key(self, client, monkeypatch):
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/send-message",
            json={"to_number": "+15550001111", "message": "hola"},
        )

        assert response.status_code == 503

    def test_rejects_wrong_api_key(self, client, monkeypatch):
        monkeypatch.setenv("SEND_MESSAGE_API_KEY", "expected-key")
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/send-message",
            json={"to_number": "+15550001111", "message": "hola"},
            headers={"x-api-key": "wrong-key"},
        )

        assert response.status_code == 403

    def test_accepts_valid_api_key(self, client, monkeypatch):
        monkeypatch.setenv("SEND_MESSAGE_API_KEY", "expected-key")
        install_assistant(monkeypatch, StubAssistant())

        response = client.post(
            "/send-message",
            json={"to_number": "+15550001111", "message": "hola"},
            headers={"x-api-key": "expected-key"},
        )

        assert response.status_code == 200
        assert response.json() == {"success": True, "sid": "SM123", "status": "queued"}
