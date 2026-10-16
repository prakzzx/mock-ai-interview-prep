"""Fakes shared by the tests. Nothing here touches the network or any hardware."""

import json
import threading
import types


def kind_of(prompt):
    """Which of the three prompts is this? ("resume", "question" or "feedback")"""
    if "expert resume parser" in prompt:
        return "resume"
    if "Generate the next interview question" in prompt:
        return "question"
    if "talent assessor, and executive coach" in prompt:
        return "feedback"
    raise AssertionError("Unknown prompt sent to the fake LLM")


class FakeLLM:
    """Stand-in for litellm.completion; records every prompt it receives."""

    def __init__(self, handler=None):
        self.handler = handler or self.default_handler
        self.prompts = []
        self._lock = threading.Lock()
        self._question_counter = 0

    def default_handler(self, prompt):
        kind = kind_of(prompt)
        if kind == "resume":
            return json.dumps(
                {"name": "Jane Doe", "resume_highlights": "Led a team of 5 engineers."}
            )
        if kind == "question":
            with self._lock:
                self._question_counter += 1
                number = self._question_counter
            return json.dumps({"next_question": f"Generated question {number}"})
        return json.dumps({"feedback": "Good answer.", "score": 8})

    def __call__(self, model=None, messages=None, **kwargs):
        prompt = messages[0]["content"]
        with self._lock:
            self.prompts.append(prompt)
        reply = self.handler(prompt)
        message = types.SimpleNamespace(content=reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    def count(self, kind):
        return sum(1 for prompt in self.prompts if kind_of(prompt) == kind)


def minimal_pdf_bytes(text):
    """Build a tiny one-page PDF that contains `text` (or no text at all if empty)."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET" if text else ""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = "%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n"
    xref_at = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n"
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    )
    return body.encode("latin-1")
