# backend/app/services/document_extractor.py
import io
import zipfile
from typing import Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument

class DocumentExtractor:
    MAX_EXTRACTED_CHARS = 2_000_000
    
    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> Tuple[str, str]:
        """
        Extrait le texte brut en limitant la charge CPU/Mémoire.
        """
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        try:
            if ext == 'pdf':
                return _extract_pdf_limited(file_bytes), "PDF"
            elif ext == 'docx':
                _validate_docx_archive(file_bytes)
                return _extract_docx_safe(file_bytes), "DOCX"
            else:
                raise ValueError(f"Format non supporté : .{ext}.")
                
        except Exception as e:
            # Keep unsupported-format errors actionable without leaking parser details.
            if ext not in {"pdf", "docx"}:
                raise ValueError(f"Format non supporté : .{ext}.") from None
            raise ValueError("Échec de l'extraction du document. Vérifiez son format et son intégrité.") from e

def _extract_pdf_limited(data: bytes, max_pages: int = 50) -> str:
    """Extraction PDF avec limite de pages pour éviter timeouts."""
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("Les PDF chiffrés ne sont pas acceptés.")
    text_parts = []
    
    total_pages = len(reader.pages)
    pages_to_read = min(total_pages, max_pages)
    
    for page_num in range(pages_to_read):
        try:
            page = reader.pages[page_num]
            page_text = page.extract_text()
            if page_text and page_text.strip():
                cleaned = ' '.join(page_text.split())
                text_parts.append(cleaned)
        except Exception:
             # Skip malformed page without exposing parser details or document data.
             continue 

    if not text_parts:
        raise ValueError("Aucun texte extractible trouvé.")
        
    # Si le document était plus long que la limite, ajouter une note
    suffix = ""
    if total_pages > max_pages:
        suffix = f"\n\n[NOTE : Document tronqué après {max_pages} pages sur {total_pages} totales]"
        
    extracted = '\n\n'.join(text_parts) + suffix
    if len(extracted) > DocumentExtractor.MAX_EXTRACTED_CHARS:
        extracted = extracted[:DocumentExtractor.MAX_EXTRACTED_CHARS] + "\n\n[NOTE : Texte tronqué à la limite de sécurité.]"
    return extracted

def _extract_docx_safe(data: bytes) -> str:
    """Extract paragraphs and table cells while respecting the global text limit."""
    doc = DocxDocument(io.BytesIO(data))
    parts = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    # DOCX tables often contain policy/control content; omitting them silently
    # loses important material for search and RAG.
    for table in getattr(doc, "tables", []):
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    if not parts:
        raise ValueError("Document Word vide ou illisible.")

    extracted = "\\n\\n".join(parts)
    if len(extracted) > DocumentExtractor.MAX_EXTRACTED_CHARS:
        extracted = extracted[:DocumentExtractor.MAX_EXTRACTED_CHARS] + "\\n\\n[NOTE : Texte tronqué à la limite de sécurité.]"
    return extracted

def _validate_docx_archive(data: bytes, max_entries: int = 1000, max_uncompressed: int = 50 * 1024 * 1024) -> None:
    """Reject malformed or suspiciously large DOCX ZIP containers before parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise ValueError("DOCX contenant trop d'éléments.")
            total_uncompressed = sum(entry.file_size for entry in entries)
            if total_uncompressed > max_uncompressed:
                raise ValueError("DOCX décompressé trop volumineux.")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Structure DOCX invalide.")
            for entry in entries:
                if entry.file_size > 0 and entry.compress_size == 0:
                    raise ValueError("Archive DOCX suspecte.")
                if entry.compress_size and entry.file_size / entry.compress_size > 1000:
                    raise ValueError("Ratio de compression DOCX suspect.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Fichier DOCX invalide.") from exc
