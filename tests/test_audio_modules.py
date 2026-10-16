"""Text-to-speech and recording helpers with pygame, edge-tts and sounddevice faked."""

import subprocess
import sys
import threading
import types
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

import utils.text_to_speech as tts
from utils import record_utils

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- fakes
class FakePygame(types.ModuleType):
    """Just enough of pygame for utils.text_to_speech."""

    def __init__(self, init_error=None):
        super().__init__("pygame")
        self.events = []
        self.loaded_path = None
        self.path_existed_when_loaded = None
        self._busy_polls = 2
        outer = self

        class Music:
            @staticmethod
            def load(path):
                outer.loaded_path = path
                outer.path_existed_when_loaded = Path(path).exists()
                outer.events.append("load")

            @staticmethod
            def play():
                outer.events.append("play")

            @staticmethod
            def get_busy():
                outer._busy_polls -= 1
                return outer._busy_polls >= 0

            @staticmethod
            def unload():
                outer.events.append("unload")

        class Mixer:
            music = Music

            @staticmethod
            def init():
                if init_error:
                    raise init_error
                outer.events.append("init")

            @staticmethod
            def quit():
                outer.events.append("quit")

        class Time:
            @staticmethod
            def wait(ms):
                outer.events.append("wait")

        self.mixer = Mixer
        self.time = Time


class FakeCommunicate:
    created = []
    save_error = None

    def __init__(self, text, voice, rate="+0%", pitch="+0Hz"):
        self.text, self.voice, self.rate, self.pitch = text, voice, rate, pitch
        FakeCommunicate.created.append(self)

    async def save(self, path):
        if FakeCommunicate.save_error:
            raise FakeCommunicate.save_error
        Path(path).write_bytes(b"fake mp3 data")


@pytest.fixture
def fake_tts(monkeypatch):
    FakeCommunicate.created = []
    FakeCommunicate.save_error = None
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommunicate)

    def install(pygame_module):
        monkeypatch.setitem(sys.modules, "pygame", pygame_module)
        return pygame_module

    return install


# ---------------------------------------------------------------- text to speech
def test_speech_is_synthesized_and_played(fake_tts):
    pygame = fake_tts(FakePygame())
    assert tts.speak_text("Hello there", voice="en-GB-SoniaNeural") is True

    spoken = FakeCommunicate.created[0]
    assert (spoken.text, spoken.voice) == ("Hello there", "en-GB-SoniaNeural")
    assert pygame.events[:3] == ["init", "load", "play"]
    assert "wait" in pygame.events  # it waited for playback to finish
    assert pygame.events[-2:] == ["unload", "quit"]
    assert pygame.path_existed_when_loaded is True
    assert not Path(pygame.loaded_path).exists()  # temp file cleaned up


def test_default_voice_is_alex(fake_tts):
    fake_tts(FakePygame())
    tts.speak_text("Hi")
    assert FakeCommunicate.created[0].voice == "en-US-GuyNeural"


def test_no_audio_device_does_not_crash(fake_tts, capsys):
    pygame = fake_tts(FakePygame(init_error=RuntimeError("No audio device")))
    assert tts.speak_text("Tell me about yourself") is False

    output = capsys.readouterr().out
    assert "No audio device" in output
    assert "Tell me about yourself" in output  # the text is still shown
    assert not Path(pygame.loaded_path or "/nonexistent").exists()
    assert "quit" in pygame.events


def test_pygame_not_installed_does_not_crash(fake_tts, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pygame", None)  # makes `import pygame` fail
    assert tts.speak_text("Question text") is False
    assert "Question text" in capsys.readouterr().out


def test_speech_service_failure_does_not_crash(fake_tts, capsys):
    pygame = fake_tts(FakePygame())
    FakeCommunicate.save_error = ConnectionError("offline")
    assert tts.speak_text("Question text") is False
    assert "offline" in capsys.readouterr().out
    assert "play" not in pygame.events


# ---------------------------------------------------------------- recording helpers
def write_wav(path, samples):
    wavfile.write(str(path), 16000, np.asarray(samples, dtype="int16"))
    return str(path)


def test_validate_audio_file(tmp_path):
    loud = write_wav(tmp_path / "loud.wav", [0, 5000, -5000, 3000])
    quiet = write_wav(tmp_path / "quiet.wav", [0, 10, -10, 5])
    empty = write_wav(tmp_path / "empty.wav", [])
    assert record_utils.validate_audio_file(loud) is True
    assert record_utils.validate_audio_file(quiet) is False
    assert record_utils.validate_audio_file(empty) is False
    assert record_utils.validate_audio_file(str(tmp_path / "missing.wav")) is False


def test_reduce_noise_uses_noisereduce_and_rewrites_the_file(tmp_path, monkeypatch):
    path = write_wav(tmp_path / "a.wav", [1000, -2000, 3000, -4000])
    calls = {}

    def fake_reduce(y, sr):
        calls["sr"] = sr
        return y * 0.5

    fake_nr = types.ModuleType("noisereduce")
    fake_nr.reduce_noise = fake_reduce
    monkeypatch.setitem(sys.modules, "noisereduce", fake_nr)

    assert record_utils.reduce_noise(path, 16000) == path
    assert calls["sr"] == 16000
    rate, data = wavfile.read(path)
    assert rate == 16000
    assert list(data) == [500, -1000, 1500, -2000]


def test_reduce_noise_leaves_empty_audio_alone(tmp_path, monkeypatch):
    path = write_wav(tmp_path / "empty.wav", [])
    fake_nr = types.ModuleType("noisereduce")
    fake_nr.reduce_noise = lambda **kwargs: pytest.fail("must not be called")
    monkeypatch.setitem(sys.modules, "noisereduce", fake_nr)
    assert record_utils.reduce_noise(path, 16000) == path


def make_fake_sounddevice(chunks):
    """A fake sounddevice whose stream delivers `chunks` and then lets Enter happen."""
    delivered = threading.Event()

    class FakeInputStream:
        def __init__(self, samplerate, channels, dtype, callback):
            self.callback = callback
            self.stopped = False

        def __enter__(self):
            for chunk in chunks:
                self.callback(
                    np.asarray(chunk, dtype="int16").reshape(-1, 1),
                    len(chunk),
                    None,
                    None,
                )
            delivered.set()
            return self

        def __exit__(self, *exc):
            return False

        def stop(self):
            self.stopped = True

    module = types.ModuleType("sounddevice")
    module.InputStream = FakeInputStream
    return module, delivered


def test_recording_stops_on_enter_and_writes_a_wav(tmp_path, monkeypatch):
    fake_sd, delivered = make_fake_sounddevice([[100, 200, 300], [400, 500]])
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    # "Enter" is pressed only after the fake stream delivered its audio
    monkeypatch.setattr("builtins.input", lambda *a: delivered.wait(5) and "")

    filename = str(tmp_path / "rec.wav")
    result, fs = record_utils.record_audio_with_interrupt(filename=filename)

    assert (result, fs) == (filename, 16000)
    rate, data = wavfile.read(filename)
    assert rate == 16000
    assert list(data.flatten()) == [100, 200, 300, 400, 500]


def test_recording_with_no_audio_writes_an_empty_wav(tmp_path, monkeypatch):
    fake_sd, delivered = make_fake_sounddevice([])
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.setattr("builtins.input", lambda *a: delivered.wait(5) and "")

    filename = str(tmp_path / "rec.wav")
    record_utils.record_audio_with_interrupt(filename=filename)
    assert record_utils.validate_audio_file(filename) is False


def test_save_audio_file_creates_folders(tmp_path):
    target = tmp_path / "audio" / "Jane" / "Jane_1.wav"
    assert record_utils.save_audio_file(b"abc", str(target)) == str(target)
    assert target.read_bytes() == b"abc"


# ---------------------------------------------------------------- lazy imports
def test_heavy_audio_libraries_are_not_imported_at_startup():
    """The web app must start without PortAudio (sounddevice) or an audio device."""
    code = (
        "import sys, utils, app, main\n"
        "heavy = ['sounddevice', 'noisereduce', 'scipy', 'pygame']\n"
        "loaded = [m for m in heavy if m in sys.modules]\n"
        "print('LOADED:' + ','.join(loaded))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "LOADED:"
