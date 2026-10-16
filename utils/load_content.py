from pypdf import PdfReader
import PyPDF2


class EmptyDocumentError(ValueError):
    """Raised when a document has no extractable text (e.g. a scanned PDF)."""


def _join_pages(pages):
    text = "".join((page.extract_text() or "") for page in pages)
    if not text.strip():
        raise EmptyDocumentError(
            "No text could be extracted from this PDF. It may be a scanned image; "
            "please upload a PDF that contains selectable text."
        )
    return text


def load_content(file_path):
    # check if pdf then below code will be executed else add read txt file
    if file_path.endswith(".pdf"):
        pdf = PdfReader(file_path)
        return _join_pages(pdf.pages)
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    else:
        print("Unsupported file format")
        return ""


def load_content_streamlit(upload_file):
    if upload_file is not None:
        # Read the PDF file
        pdf_reader = PyPDF2.PdfReader(upload_file)
        # Extract the content
        return _join_pages(pdf_reader.pages)
