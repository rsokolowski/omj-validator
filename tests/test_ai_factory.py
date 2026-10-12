"""create_ai_provider follows the persisted active model."""

import pytest

from app.ai import factory
from app.ai.config_store import ActiveModel
from app.ai.factory import AIProviderError
from app.config import settings


class FakeProvider:
    def __init__(self, provider, model):
        self.provider_name, self.model_name = provider, model


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    factory.reset_provider_cache()
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "a-key")
    monkeypatch.setattr(settings, "anthropic_processor_approved", True)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(factory, "_construct", lambda provider, model: FakeProvider(provider, model))
    yield
    factory.reset_provider_cache()


def use(monkeypatch, provider, model):
    monkeypatch.setattr(factory, "get_active_model", lambda: ActiveModel(provider, model, "db"))


def test_one_instance_per_pair(monkeypatch):
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    first = factory.create_ai_provider()
    assert factory.create_ai_provider() is first
    use(monkeypatch, "anthropic", "claude-sonnet-5-5")
    second = factory.create_ai_provider()
    assert second is not first and second.model_name == "claude-sonnet-5-5"


def test_missing_key_raises_in_build(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(AIProviderError):
        factory.build_provider("anthropic", "claude-opus-5-5")


def test_unapproved_anthropic_falls_back_to_env_gemini(monkeypatch, caplog):
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    provider = factory.create_ai_provider()
    assert (provider.provider_name, provider.model_name) == ("gemini", "gemini-3.8-flash")
    assert "not approved" in caplog.text


def test_active_provider_without_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    assert factory.create_ai_provider().provider_name == "gemini"


def test_env_provider_without_key_still_raises(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    use(monkeypatch, "gemini", "gemini-3.8-flash")
    with pytest.raises(AIProviderError):
        factory.create_ai_provider()


def test_unknown_provider_raises():
    with pytest.raises(AIProviderError):
        factory.build_provider("openai", "gpt")
