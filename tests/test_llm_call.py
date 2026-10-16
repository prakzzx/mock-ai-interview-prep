import importlib
import json
import os
import subprocess
import sys
import textwrap
import types
from pathlib import Path

import pytest

from utils import llm_call
from utils.llm_call import LLMResponseError, get_json_from_llm, parse_json_response

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- parse_json_response
def test_clean_json():
    assert parse_json_response('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_fenced_json_with_language_tag():
    reply = '```json\n{"feedback": "Nice", "score": 7}\n```'
    assert parse_json_response(reply) == {"feedback": "Nice", "score": 7}


def test_fenced_json_without_language_tag():
    assert parse_json_response('```\n{"a": 1}\n```') == {"a": 1}


def test_fenced_json_with_surrounding_whitespace():
    assert parse_json_response('\n\n  ```json\n{"a": 1}\n```  \n') == {"a": 1}


def test_json_with_surrounding_text():
    reply = 'Sure! Here you go:\n{"next_question": "Why us?"}\nHope that helps.'
    assert parse_json_response(reply) == {"next_question": "Why us?"}


def test_fence_inside_surrounding_text():
    reply = 'Here is the result:\n```json\n{"a": {"b": [1, 2]}}\n```\nDone.'
    assert parse_json_response(reply) == {"a": {"b": [1, 2]}}


def test_nested_objects_and_braces_in_strings():
    reply = 'x {"a": {"b": "curly } brace"}, "c": 2} y'
    assert parse_json_response(reply) == {"a": {"b": "curly } brace"}, "c": 2}


def test_first_block_invalid_second_valid():
    assert parse_json_response('{oops} then {"ok": true}') == {"ok": True}


def test_trailing_comma_from_the_prompt_template_is_tolerated():
    reply = '{"name": "Jane", "resume_highlights": "Did things",\n}'
    assert parse_json_response(reply) == {
        "name": "Jane",
        "resume_highlights": "Did things",
    }


def test_original_strip_bug_is_gone():
    # str.strip("```json") strips *characters*; a reply ending in such letters broke.
    reply = '```json\n{"feedback": "Strong opinion", "score": 9}\n```\nson'
    assert parse_json_response(reply)["score"] == 9


@pytest.mark.parametrize(
    "reply", ["not json at all", "{broken", "[1, 2, 3]", "", "   ", None, 42]
)
def test_invalid_raises_llm_response_error(reply):
    with pytest.raises(LLMResponseError):
        parse_json_response(reply)


# ---------------------------------------------------------------- retry path
def test_retry_once_after_parse_failure(fake_llm):
    replies = iter(["sorry, no JSON here", json.dumps({"ok": 1})])
    fake = fake_llm(lambda prompt: next(replies))
    assert get_json_from_llm("prompt") == {"ok": 1}
    assert len(fake.prompts) == 2


def test_gives_up_after_one_retry(fake_llm):
    fake = fake_llm(lambda prompt: "still not json")
    with pytest.raises(LLMResponseError):
        get_json_from_llm("prompt")
    assert len(fake.prompts) == 2


def test_no_retry_when_first_reply_is_valid(fake_llm):
    fake = fake_llm(lambda prompt: '{"a": 1}')
    get_json_from_llm("prompt")
    assert len(fake.prompts) == 1


def test_llm_is_called_with_configured_model(monkeypatch):
    seen = {}

    def capture(model=None, messages=None, **kwargs):
        seen["model"] = model
        seen["messages"] = messages
        message = types.SimpleNamespace(content='{"a": 1}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    monkeypatch.setattr(llm_call, "completion", capture)
    monkeypatch.setattr(llm_call, "LLM_MODEL", "test/model")
    assert llm_call.get_response_from_llm("hello") == '{"a": 1}'
    assert seen["model"] == "test/model"
    assert seen["messages"] == [{"role": "user", "content": "hello"}]


# ---------------------------------------------------------------- load_dotenv fix
def test_llm_model_default_and_override(monkeypatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    try:
        monkeypatch.delenv("LLM_MODEL", raising=False)
        assert importlib.reload(llm_call).LLM_MODEL == "mistral/mistral-large-latest"
        monkeypatch.setenv("LLM_MODEL", "openai/gpt-test")
        assert importlib.reload(llm_call).LLM_MODEL == "openai/gpt-test"
        monkeypatch.setenv("LLM_MODEL", "")
        assert importlib.reload(llm_call).LLM_MODEL == "mistral/mistral-large-latest"
    finally:
        monkeypatch.undo()
        importlib.reload(llm_call)


def test_dotenv_is_loaded_before_llm_model_is_read(tmp_path):
    """Copy utils/ next to a .env file and import it in a clean interpreter."""
    import shutil

    shutil.copytree(
        ROOT / "utils", tmp_path / "utils", ignore=shutil.ignore_patterns("__pycache__")
    )
    (tmp_path / ".env").write_text('LLM_MODEL="test/from-dotenv"\n', encoding="utf-8")
    code = textwrap.dedent(
        """
        import utils.llm_call as m
        print(m.LLM_MODEL)
        """
    )
    env = {k: v for k, v in os.environ.items() if k != "LLM_MODEL"}
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "test/from-dotenv"


@pytest.mark.parametrize("filename", ["app.py", "main.py"])
def test_entry_points_call_load_dotenv_before_importing_utils(filename):
    source = (ROOT / filename).read_text(encoding="utf-8")
    assert source.index("load_dotenv()") < source.index("from utils import")


def test_llm_call_calls_load_dotenv_before_reading_the_model():
    source = (ROOT / "utils" / "llm_call.py").read_text(encoding="utf-8")
    assert source.index("load_dotenv()") < source.index("LLM_MODEL =")
