import io
import math
import struct
import wave

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers import Providers

EMERGENCY_NUMBER = "TEST-EMERGENCY-000"


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        app_env="test", database_url=f"sqlite:///{tmp_path}/test.db", app_secret_key="t" * 40,
        emergency_contact_number=EMERGENCY_NUMBER, rate_limit_per_minute=10_000, rate_limit_heavy_per_minute=10_000,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def migrate(settings: Settings) -> None:
    cfg = Config("alembic.ini")
    from app.core import config as cfg_module

    cfg_module.get_settings.cache_clear()
    import os

    os.environ["DATABASE_URL"] = settings.database_url
    try:
        command.upgrade(cfg, "head")
    finally:
        os.environ.pop("DATABASE_URL", None)
        cfg_module.get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = make_settings(tmp_path)
    migrate(s)
    return s


@pytest.fixture
def make_client(settings, tmp_path):
    def _make(providers: Providers | None = None, **overrides) -> TestClient:
        # Rebuild (not model_copy) so overrides are validated, e.g. strings become SecretStr.
        s = make_settings(tmp_path, **overrides) if overrides else settings
        return TestClient(create_app(s, providers or Providers()), raise_server_exceptions=False)

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


class Chat:
    """Small helper that drives one conversation through the HTTP API."""

    def __init__(self, client: TestClient, language: str | None = "hi") -> None:
        self.client = client
        r = client.post("/api/v1/conversations", json={"language": language})
        assert r.status_code == 201, r.text
        body = r.json()
        self.id, self.headers, self.created = body["conversation_id"], {"X-Conversation-Token": body["access_token"]}, body
        self.last: dict = {}

    def say(self, text: str, **extra) -> dict:
        r = self.client.post(f"/api/v1/conversations/{self.id}/messages", json={"text": text, **extra}, headers=self.headers)
        assert r.status_code == 200, r.text
        self.last = r.json()
        return self.last

    def answer_until_final(self, answers: dict[str, str], default: str = "nahi", limit: int = 15) -> dict:
        """Answer each question by id (or default) until a final triage appears."""
        for _ in range(limit):
            if self.last.get("triage"):
                return self.last
            qid = self.last["question"]["question_id"]
            self.say(answers.get(qid, default))
        raise AssertionError("conversation did not finish")

    @property
    def level(self) -> str | None:
        t = self.last.get("triage")
        return t["triage_level"] if t else None


@pytest.fixture
def chat(client):
    return lambda language="hi": Chat(client, language)


def wav_bytes(seconds: float = 1.0, amplitude: int = 8000, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate)))
        w.writeframes(frames)
    return buf.getvalue()
