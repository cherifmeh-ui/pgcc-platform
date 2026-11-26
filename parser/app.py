"""Minimal authenticated PDF/DOCX extraction service for the isolated parser container."""
import asyncio
import hmac
import os
import re
import threading
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from document_extractor import DocumentExtractor

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
TOKEN = os.environ.get("PARSER_SHARED_TOKEN", "")
_PARSE_SLOTS = threading.BoundedSemaphore(value=2)
if len(TOKEN) < 32:
    raise RuntimeError("PARSER_SHARED_TOKEN must contain at least 32 characters")

app = FastAPI(title="PGCC isolated document parser", docs_url=None, redoc_url=None)

class ExtractionResult(BaseModel):
    text: str
    detected_format: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/v1/extract", response_model=ExtractionResult)
async def extract_document(
    file: UploadFile = File(...),
    x_parser_token: str = Header(default=""),
):
    if not hmac.compare_digest(x_parser_token, TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    filename = (file.filename or "").replace("\\\\", "/").split("/")[-1]
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).strip(" .")
    if not filename or len(filename) > 200:
        raise HTTPException(status_code=400, detail="Invalid filename")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"pdf", "docx"}:
        raise HTTPException(status_code=415, detail="Unsupported document format")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty document")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document too large")
    if extension == "pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF signature")
    if extension == "docx" and not data.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Invalid DOCX signature")
    if not _PARSE_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Parser capacity temporarily exhausted")
    task = asyncio.create_task(
        asyncio.to_thread(DocumentExtractor.extract_text, data, filename)
    )
    try:
        # Shield the worker: cancellation of the HTTP request must not release
        # the concurrency slot while the native parser thread is still running.
        text, detected_format = await asyncio.wait_for(asyncio.shield(task), timeout=20)
    except asyncio.TimeoutError as exc:
        task.add_done_callback(lambda _task: _PARSE_SLOTS.release())
        raise HTTPException(status_code=408, detail="Document parsing timed out") from exc
    except ValueError as exc:
        _PARSE_SLOTS.release()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        _PARSE_SLOTS.release()
        raise
    else:
        _PARSE_SLOTS.release()
    return ExtractionResult(text=text, detected_format=detected_format)
