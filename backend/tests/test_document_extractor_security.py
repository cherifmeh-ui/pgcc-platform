import pytest

from app.services import document_extractor
from app.services.document_extractor import DocumentExtractor


def test_unsupported_extension_has_explicit_error():
    with pytest.raises(ValueError, match="non supporté"):
        DocumentExtractor.extract_text(b"ignored", "file.exe")


def test_parser_error_does_not_expose_internal_details(monkeypatch):
    def fail_parser(_data):
        raise RuntimeError("secret parser internals")

    monkeypatch.setattr(document_extractor, "_extract_pdf_limited", fail_parser)
    with pytest.raises(ValueError) as error:
        DocumentExtractor.extract_text(b"%PDF-", "report.pdf")
    assert "secret parser internals" not in str(error.value)


def test_pdf_extraction_is_truncated_at_character_limit(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "A" * 500

    class FakeReader:
        def __init__(self, _stream, strict=True):
            self.is_encrypted = False
            self.pages = [FakePage(), FakePage(), FakePage()]

    monkeypatch.setattr(document_extractor, "PdfReader", FakeReader)
    monkeypatch.setattr(DocumentExtractor, "MAX_EXTRACTED_CHARS", 700)
    text = document_extractor._extract_pdf_limited(b"%PDF-")
    assert len(text) <= 800
    assert "tronqué à la limite de sécurité" in text
    assert "\n\n" in text



def test_docx_extraction_is_truncated_at_character_limit(monkeypatch):
    class FakeParagraph:
        text = "B" * 500


    class FakeDoc:
        paragraphs = [FakeParagraph(), FakeParagraph(), FakeParagraph()]

    monkeypatch.setattr(document_extractor, "DocxDocument", lambda _stream: FakeDoc())
    monkeypatch.setattr(DocumentExtractor, "MAX_EXTRACTED_CHARS", 700)
    text = document_extractor._extract_docx_safe(b"not relevant in fake")
    assert len(text) <= 800
    assert "tronqué à la limite de sécurité" in text



def test_docx_extraction_includes_table_cells(monkeypatch):
    class FakeParagraph:
        text = "Policy paragraph"

    class FakeCell:
        def __init__(self, text):
            self.text = text

    class FakeRow:
        cells = [FakeCell("Control A"), FakeCell("Implemented")]

    class FakeTable:
        rows = [FakeRow()]

    class FakeDoc:
        paragraphs = [FakeParagraph()]
        tables = [FakeTable()]

    monkeypatch.setattr(document_extractor, "DocxDocument", lambda _stream: FakeDoc())
    extracted = document_extractor._extract_docx_safe(b"mock")

    assert "Policy paragraph" in extracted
    assert "Control A | Implemented" in extracted
    assert "Policy paragraph\n\nControl A | Implemented" in extracted

def test_docx_archive_rejects_non_zip_payload():
    with pytest.raises(ValueError, match="Échec de l'extraction"):
        DocumentExtractor.extract_text(b"PK-not-a-real-zip", "broken.docx")


def test_docx_archive_requires_word_document_part():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    with pytest.raises(ValueError, match="Échec de l'extraction"):
        DocumentExtractor.extract_text(buffer.getvalue(), "missing-document.docx")


def test_docx_archive_rejects_excessive_entry_count(monkeypatch):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/styles.xml", "<styles/>")
    with pytest.raises(ValueError, match="Échec de l'extraction"):
        DocumentExtractor.extract_text(buffer.getvalue(), "many-entries.docx")
    # Exercise the archive guard's configurable bound directly.
    with pytest.raises(ValueError, match="trop d'éléments"):
        document_extractor._validate_docx_archive(buffer.getvalue(), max_entries=1)


def test_docx_archive_rejects_excessive_uncompressed_size():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", "x" * 128)
    with pytest.raises(ValueError, match="trop volumineux"):
        document_extractor._validate_docx_archive(
            buffer.getvalue(), max_uncompressed=64
        )


def test_docx_archive_rejects_suspicious_compression_ratio():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "A" * 2_000_000)
    with pytest.raises(ValueError, match="Ratio de compression"):
        document_extractor._validate_docx_archive(buffer.getvalue())

