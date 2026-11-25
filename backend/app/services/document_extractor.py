# backend/app/services/document_extractor.py
import io
import zipfile
from typing import Tuple

from pypdf import PdfReader
from docx import Document as DocxDocument


class DocumentExtractor:
    MAX_EXTRACTED_CHARS = 2_000_000
    MAX_PDF_PAGES = 50

    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> Tuple[str, str]:
        """Extract text with strict format validation and bounded output."""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        try:
            if ext == "pdf":
                return _extract_pdf_limited(file_bytes), "PDF"
            if ext == "docx":
                _validate_docx_archive(file_bytes)
                return _extract_docx_safe(file_bytes), "DOCX"
            raise ValueError(f"Format non supporté : .{ext}.")
        except Exception as exc:
            if ext not in {"pdf", "docx"}:
                raise ValueError(f"Format non supporté : .{ext}.") from None
            # Do not leak parser internals or fragments of document content.
            raise ValueError(
                "Échec de l'extraction du document. Vérifiez son format et son intégrité."
            ) from exc


def _bounded_text(parts, value: str, current_length: int):
    """Append at most the remaining character budget; return (length, truncated)."""
    if not value:
        return current_length, False
    remaining = DocumentExtractor.MAX_EXTRACTED_CHARS - current_length
    if remaining <= 0:
        return current_length, True
    if len(value) > remaining:
        parts.append(value[:remaining])
        return DocumentExtractor.MAX_EXTRACTED_CHARS, True
    parts.append(value)
    return current_length + len(value), False


def _finish_extraction(parts, truncated: bool) -> str:
    extracted = "\\n\\n".join(parts)
    if truncated:
        extracted += "\\n\\n[NOTE : Texte tronqué à la limite de sécurité.]"
    return extracted


def _extract_pdf_limited(data: bytes, max_pages: int = DocumentExtractor.MAX_PDF_PAGES) -> str:
    """Extract at most max_pages and MAX_EXTRACTED_CHARS; fail on unreadable pages."""
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("Les PDF chiffrés ne sont pas acceptés.")

    total_pages = len(reader.pages)
    pages_to_read = min(total_pages, max_pages)
    parts = []
    current_length = 0
    truncated = total_pages > max_pages

    for page_num in range(pages_to_read):
        try:
            page_text = reader.pages[page_num].extract_text()
        except Exception as exc:
            # A partial index is unsafe: it would silently omit document content.
            raise ValueError("Une page PDF n'a pas pu être extraite.") from exc
        if not page_text or not page_text.strip():
            continue
        cleaned = " ".join(page_text.split())
        current_length, hit_limit = _bounded_text(parts, cleaned, current_length)
        if hit_limit:
            truncated = True
            break

    if not parts:
        raise ValueError("Aucun texte extractible trouvé.")
    return _finish_extraction(parts, truncated)


def _extract_docx_safe(data: bytes) -> str:
    """Extract paragraphs and table cells without accumulating unbounded text."""
    doc = DocxDocument(io.BytesIO(data))
    parts = []
    current_length = 0
    truncated = False

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            current_length, truncated = _bounded_text(parts, text, current_length)
            if truncated:
                break

    if not truncated:
        for table in getattr(doc, "tables", []):
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    current_length, truncated = _bounded_text(
                        parts, " | ".join(cells), current_length
                    )
                    if truncated:
                        break
            if truncated:
                break

    if not parts:
        raise ValueError("Document Word vide ou illisible.")
    return _finish_extraction(parts, truncated)


def _validate_docx_archive(
    data: bytes,
    max_entries: int = 1000,
    max_uncompressed: int = 50 * 1024 * 1024,
) -> None:
    """Reject malformed or suspiciously large DOCX ZIP containers before parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise ValueError("DOCX contenant trop d'éléments.")
            total_uncompressed = sum(entry.file_size for entry in entries)
            if total_uncompressed > max_uncompressed:
                raise ValueError("DOCX décompressé trop volumineux.")
            names = [entry.filename for entry in entries]
            if "word/document.xml" not in names:
                raise ValueError("Structure DOCX invalide.")
            if len(names) != len(set(names)):
                raise ValueError("Archive DOCX contenant des entrées dupliquées.")
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise ValueError("Archive DOCX chiffrée non acceptée.")
                if entry.file_size > 0 and entry.compress_size == 0:
                    raise ValueError("Archive DOCX suspecte.")
                if entry.compress_size and entry.file_size / entry.compress_size > 1000:
                    raise ValueError("Ratio de compression DOCX suspect.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Fichier DOCX invalide.") from exc
