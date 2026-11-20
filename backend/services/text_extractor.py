# backend/services/text_extractor.py
import io
from typing import Optional, Tuple

# Bibliothèque pour PDF
try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError("Installez 'pypdf2' via pip install pypdf2")

# Bibliothèque pour DOCX
try:
    from docx import Document as DocxDocument
except ImportError:
    raise ImportError("Installez 'python-docx' via pip install python-docx")


class TextExtractorService:
    
    @staticmethod
    def extract_from_pdf(file_bytes: bytes) -> Tuple[str, int]:
        """
        Extrait le texte d'un PDF et retourne (texte_brut, nombre_pages).
        Gère les erreurs de lecture proprement.
        """
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                # Nettoyage basique : remplacer multiples espaces/newlines par un seul espace
                cleaned_page = " ".join(page_text.split())
                if cleaned_page:
                    text_parts.append(f"[Page {page_num}]\n{cleaned_page}")
            
            full_text = "\n\n".join(text_parts)
            return full_text.strip(), len(reader.pages)
            
        except Exception as e:
            print(f"❌ Erreur extraction PDF : {str(e)}")
            return "", 0

    @staticmethod
    def extract_from_docx(file_bytes: bytes) -> Tuple[str, int]:
        """
        Extrait le texte d'un DOCX et retourne (texte_brut, nombre_paragraphes).
        """
        try:
            doc = DocxDocument(io.BytesIO(file_bytes))
            paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            
            # On considère chaque paragraphe non-vide comme une "unité" logique
            num_units = len(paragraphs)
            full_text = "\n\n".join(paragraphs)
            
            return full_text.strip(), num_units
            
        except Exception as e:
            print(f"❌ Erreur extraction DOCX : {str(e)}")
            return "", 0

    @classmethod
    def extract(cls, file_bytes: bytes, filename: str) -> Tuple[str, int, str]:
        """
        Point d'entrée unique qui dispatche selon l'extension du fichier.
        Retourne : (texte, nb_unités, type_fichier_détecté)
        """
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            text, count = cls.extract_from_pdf(file_bytes)
            return text, count, "pdf"
        elif ext == 'docx':
            text, count = cls.extract_from_docx(file_bytes)
            return text, count, "docx"
        else:
            raise ValueError(f"Format de fichier non supporté : .{ext}. Utilisez PDF ou DOCX.")