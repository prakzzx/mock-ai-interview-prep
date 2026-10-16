"""Shared fixtures. Nothing here touches the network or any hardware."""

import pytest

from helpers import FakeLLM


@pytest.fixture
def fake_llm(monkeypatch):
    """Factory that installs a FakeLLM as litellm's `completion` used by the app."""
    from utils import llm_call

    def install(handler=None):
        fake = FakeLLM(handler)
        monkeypatch.setattr(llm_call, "completion", fake)
        return fake

    return install
