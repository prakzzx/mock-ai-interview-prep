import importlib
import io

import pytest

from helpers import minimal_pdf_bytes

from utils.load_content import EmptyDocumentError, load_content, load_content_streamlit

lc = importlib.import_module("utils.load_content")  # not the function


def test_pdf_with_text_is_read_from_disk(tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(minimal_pdf_bytes("Jane Doe Engineer"))
    assert "Jane Doe Engineer" in load_content(str(path))


def test_uploaded_pdf_with_text_is_read(tmp_path):
    upload = io.BytesIO(minimal_pdf_bytes("Jane Doe Engineer"))
    assert "Jane Doe Engineer" in load_content_streamlit(upload)


def test_pdf_without_text_raises_a_clear_error_for_uploads():
    upload = io.BytesIO(minimal_pdf_bytes(""))
    with pytest.raises(EmptyDocumentError, match="No text could be extracted"):
        load_content_streamlit(upload)


def test_pdf_without_text_raises_a_clear_error_from_disk(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(minimal_pdf_bytes(""))
    with pytest.raises(EmptyDocumentError):
        load_content(str(path))


def test_pages_that_return_none_are_handled():
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    assert lc._join_pages([Page(None), Page("Hello")]) == "Hello"
    with pytest.raises(EmptyDocumentError):
        lc._join_pages([Page(None), Page("   ")])


def test_text_files_are_read(tmp_path):
    path = tmp_path / "jd.txt"
    path.write_text("Senior Developer é", encoding="utf-8")
    assert load_content(str(path)) == "Senior Developer é"


def test_unsupported_format_returns_empty_string(capsys):
    assert load_content("notes.docx") == ""
    assert "Unsupported file format" in capsys.readouterr().out


def test_no_upload_returns_none():
    assert load_content_streamlit(None) is None
