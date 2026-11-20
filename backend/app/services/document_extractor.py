# backend/app/services/document_extractor.py
import io
from typing import Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument

class DocumentExtractor:
    
    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> Tuple[str, str]:
        """
        Extrait le texte brut en limitant la charge CPU/Mémoire.
        """
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        try:
            if ext == 'pdf':
                return _extract_pdf_limited(file_bytes), "PDF"
            elif ext in ['doc', 'docx']:
                return _extract_docx_safe(file_bytes), "DOCX"
            else:
                raise ValueError(f"Format non supporté : .{ext}.")
                
        except Exception as e:
            print(f"❌ Erreur extraction {filename}: {str(e)}")
            # Ne pas lever d'exception bloquante ici, retourner une erreur propre
            raise ValueError(f"Echec extraction : {str(e)[:80]}...")

def _extract_pdf_limited(data: bytes, max_pages: int = 50) -> str:
    """Extraction PDF avec limite de pages pour éviter timeouts."""
    reader = PdfReader(io.BytesIO(data))
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
        except Exception as e_page:
             print(f"⚠️ Skip page {page_num + 1} : {e_page}")
             continue 

    if not text_parts:
        raise ValueError("Aucun texte extractible trouvé.")
        
    # Si le document était plus long que la limite, ajouter une note
    suffix = ""
    if total_pages > max_pages:
        suffix = f"\n\n[NOTE : Document tronqué après {max_pages} pages sur {total_pages} totales]"
        
    return '\n\n'.join(text_parts) + suffix

def _extract_docx_safe(data: bytes) -> str:
    """Extraction Word robuste."""
    doc = DocxDocument(io.BytesIO(data))
    paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    
    if not paragraphs:
        raise ValueError("Document Word vide ou illisible.")
        
    return '\n\n'.join(paragraphs)