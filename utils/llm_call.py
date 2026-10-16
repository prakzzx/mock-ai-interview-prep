"""LLM access through LiteLLM, plus robust parsing of the JSON the prompts ask for."""

import json
import os
import re

from dotenv import load_dotenv

# LLM_MODEL is read at import time below, so the .env file must be loaded first.
load_dotenv()

from litellm import completion  # noqa: E402

LLM_MODEL = os.environ.get("LLM_MODEL") or "groq/openai/gpt-oss-20b"


class LLMResponseError(Exception):
    """Raised when the LLM reply cannot be turned into a JSON object."""


def get_response_from_llm(prompt):
    """
    Calls the LLM and returns the response.

    Args:
        prompt (str): The string to prompt the LLM with.

    Returns:
        str: The response from the LLM.
    """
    response = completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


_FENCE_RE = re.compile(r"^```[A-Za-z0-9_+-]*[ \t]*\r?\n?(.*?)\r?\n?```$", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def _strip_code_fences(text):
    """Remove a surrounding Markdown code fence (``` or ```json) if there is one."""
    text = text.strip()
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _first_json_object(text):
    """Return the first JSON object ({...}) that can be decoded from text, or None."""
    decoder = json.JSONDecoder()
    position = text.find("{")
    while position != -1:
        try:
            value, _ = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict):
            return value
        position = text.find("{", position + 1)
    return None


def parse_json_response(response):
    """
    Parse the JSON object contained in an LLM reply.

    Code fences are removed, then the first {...} block is decoded with json.loads
    semantics. A trailing comma before a closing brace (which the basic_details prompt
    template itself shows) is tolerated as a fallback.

    Raises:
        LLMResponseError: if no valid JSON object can be found.
    """
    if not isinstance(response, str) or not response.strip():
        raise LLMResponseError("The LLM returned an empty response.")

    cleaned = _strip_code_fences(response)
    for candidate in (cleaned, _TRAILING_COMMA_RE.sub(r"\1", cleaned)):
        result = _first_json_object(candidate)
        if result is not None:
            return result

    preview = cleaned[:200].replace("\n", " ")
    raise LLMResponseError(
        f"Could not find a valid JSON object in the LLM response: {preview}"
    )


def get_json_from_llm(prompt, retries=1):
    """
    Call the LLM and parse its reply as a JSON object.

    If the reply cannot be parsed, the LLM call is repeated up to `retries` more times
    (default: once) before LLMResponseError is raised.
    """
    last_error = None
    for _ in range(retries + 1):
        raw = get_response_from_llm(prompt)
        try:
            return parse_json_response(raw)
        except LLMResponseError as error:
            last_error = error
    raise last_error
