import pytest
from speechmatics.models import ServerMessageType

from utils import transcript_audio
from utils.transcript_audio import TranscriptionError, transcribe_with_speechmatics


class FakeWebsocketClient:
    """Replays canned AddTranscript messages through the registered handler."""

    instances = []
    messages = []
    error = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.handlers = {}
        self.conf = None
        self.audio_bytes = None
        FakeWebsocketClient.instances.append(self)

    def add_event_handler(self, event_name, event_handler):
        self.handlers[event_name] = event_handler

    def run_synchronously(self, audio_file, conf):
        self.conf = conf
        self.audio_bytes = audio_file.read()
        if FakeWebsocketClient.error:
            raise FakeWebsocketClient.error
        handler = self.handlers[ServerMessageType.AddTranscript]
        for message in FakeWebsocketClient.messages:
            handler(message)


def word(text):
    return {"type": "word", "alternatives": [{"content": text}]}


def punct(text):
    return {"type": "punctuation", "alternatives": [{"content": text}]}


@pytest.fixture
def fake_client(monkeypatch, tmp_path):
    FakeWebsocketClient.instances = []
    FakeWebsocketClient.messages = []
    FakeWebsocketClient.error = None
    monkeypatch.setattr(transcript_audio, "WebsocketClient", FakeWebsocketClient)
    monkeypatch.setenv("SPEECHMATICS_API_KEY", "test-key")
    audio = tmp_path / "answer.wav"
    audio.write_bytes(b"RIFF....fake audio bytes")
    return audio


def test_transcript_is_assembled_exactly_like_the_original(fake_client):
    FakeWebsocketClient.messages = [
        {"results": [word("Hello"), word("world"), punct(".")]},
        {"metadata": "ignored: no results key"},
        {"results": [{"type": "word"}]},  # no alternatives: ignored
        {"results": [word("I"), word("am"), word("here"), punct("!")]},
    ]
    assert transcribe_with_speechmatics(str(fake_client)) == "Hello world. I am here!"


def test_protocol_settings(fake_client):
    FakeWebsocketClient.messages = [{"results": [word("Hi")]}]
    transcribe_with_speechmatics(str(fake_client))

    client = FakeWebsocketClient.instances[0]
    assert client.api_key == "test-key"
    assert set(client.handlers) == {
        ServerMessageType.AddTranscript
    }  # no partials handler
    assert client.conf.language == "en"
    assert client.conf.enable_partials is False
    assert client.conf.max_delay == 5
    assert client.audio_bytes == b"RIFF....fake audio bytes"


def test_language_can_be_changed(fake_client):
    FakeWebsocketClient.messages = [{"results": [word("Hola")]}]
    transcribe_with_speechmatics(str(fake_client), transcription_language="es")
    assert FakeWebsocketClient.instances[0].conf.language == "es"


def test_missing_api_key_raises(fake_client, monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_API_KEY")
    with pytest.raises(TranscriptionError, match="SPEECHMATICS_API_KEY"):
        transcribe_with_speechmatics(str(fake_client))
    assert FakeWebsocketClient.instances == []  # never even connected


def test_missing_audio_file_raises(fake_client, tmp_path):
    with pytest.raises(TranscriptionError, match="not found"):
        transcribe_with_speechmatics(str(tmp_path / "nope.wav"))


def test_empty_audio_file_raises(fake_client, tmp_path):
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(TranscriptionError, match="No audio recorded"):
        transcribe_with_speechmatics(str(empty))


def test_no_speech_raises_instead_of_returning_text(fake_client):
    FakeWebsocketClient.messages = []
    with pytest.raises(TranscriptionError, match="No speech detected"):
        transcribe_with_speechmatics(str(fake_client))


def test_client_failure_raises_transcription_error(fake_client):
    FakeWebsocketClient.error = RuntimeError("socket closed")
    with pytest.raises(TranscriptionError, match="Transcription failed: socket closed"):
        transcribe_with_speechmatics(str(fake_client))


def test_errors_are_never_returned_as_a_transcript(fake_client, monkeypatch):
    """Regression for the original bug: error strings used to become the answer."""
    monkeypatch.delenv("SPEECHMATICS_API_KEY")
    try:
        result = transcribe_with_speechmatics(str(fake_client))
    except TranscriptionError:
        result = None
    assert result is None
