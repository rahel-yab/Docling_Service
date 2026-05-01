import base64
from binascii import Error as BinasciiError
from tempfile import NamedTemporaryFile
from typing import Optional, Any
from functools import lru_cache
import re

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


class ParseRequest(BaseModel):
    document_url: Optional[str] = None
    source_path: Optional[str] = None
    file_base64: Optional[str] = None
    file_name: Optional[str] = None
    company_id: Optional[str] = None
    company_url: Optional[str] = None
    knowledge_source_id: Optional[str] = None


app = FastAPI(title="Docling Parser")


def _guess_document_suffix(*values: str | None) -> str:
    joined = " ".join(value.lower() for value in values if value)
    if ".docx" in joined or "officedocument.wordprocessingml.document" in joined:
        return ".docx"
    if ".doc" in joined or "msword" in joined:
        return ".doc"
    return ".pdf"


@lru_cache(maxsize=1)
def get_converter() -> Any:
    # Lazy init prevents slow model loading from blocking server port binding on startup.
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse")
async def parse_document(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    payload: ParseRequest | None = None
    uploaded_document: Any | None = None
    uploaded_file_name: str | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_document = form.get("document_file") or form.get("file") or form.get("pdf")
        if uploaded_document is not None:
            uploaded_file_name = getattr(uploaded_document, "filename", None)

        document_url = form.get("document_url")
        if document_url:
            payload = ParseRequest(
                document_url=document_url,
                company_id=form.get("company_id"),
                company_url=form.get("company_url"),
                knowledge_source_id=form.get("knowledge_source_id"),
            )
    else:
        body = await request.json()
        payload = ParseRequest.model_validate(body)

        # Backward compatibility for clients that send source_path.
        if payload.document_url is None and payload.source_path:
            payload.document_url = payload.source_path

    if payload is None or (
        payload.document_url is None
        and payload.file_base64 is None
        and uploaded_document is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide either document_url (or source_path), file_base64, "
                "or an uploaded document as document_file/file/pdf."
            ),
        )

    if payload is not None and payload.document_url:
        def _convert_google_url_to_pdf(url: str) -> str:
            m = re.search(r"https?://docs\.google\.com/document/d/([^/]+)", url)
            if m:
                return f"https://docs.google.com/document/d/{m.group(1)}/export?format=pdf"
            m = re.search(r"https?://drive\.google\.com/file/d/([^/]+)", url)
            if m:
                return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
            if "drive.google.com" in url:
                m = re.search(r"[?&]id=([^&]+)", url)
                if m:
                    return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
            return url

        original_url = payload.document_url
        payload.document_url = _convert_google_url_to_pdf(payload.document_url)

        try:
            response = requests.get(payload.document_url, timeout=30)
            response.raise_for_status()
        except Exception as exc:
            detail = f"Unable to fetch document URL: {exc}"
            if payload.document_url != original_url:
                detail += f" (rewrote {original_url} -> {payload.document_url})"
            raise HTTPException(status_code=400, detail=detail) from exc

        pdf_bytes = response.content
        content_type = response.headers.get("content-type", "").lower()
        suffix = _guess_document_suffix(payload.file_name, content_type, payload.document_url)
        if suffix == ".pdf" and "pdf" not in content_type and not pdf_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Fetched URL did not return a PDF. If this is a Google Doc, use an"
                    " export URL like '/export?format=pdf' or make the document accessible to"
                    " anyone-with-link."
                ),
            )
    elif payload is not None and payload.file_base64:
        try:
            pdf_bytes = base64.b64decode(payload.file_base64, validate=True)
        except (BinasciiError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 document payload: {exc}") from exc
    elif uploaded_document is not None:
        pdf_bytes = await uploaded_document.read()
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                "Missing document input. Provide document_url (or source_path), "
                "file_base64, or upload a document as document_file/file/pdf."
            ),
        )

    temp_suffix = _guess_document_suffix(
        payload.file_name if payload else None,
        uploaded_file_name,
        payload.document_url if payload else None,
    )

    with NamedTemporaryFile(suffix=temp_suffix, delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        try:
            result = get_converter().convert(tmp.name)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Docling conversion failed: {exc}") from exc

    content = result.document.export_to_markdown()
    metadata = {
        "source_url": payload.document_url if payload else None,
        "file_name": payload.file_name if payload else None,
        "company_id": payload.company_id if payload else None,
        "company_url": payload.company_url if payload else None,
        "knowledge_source_id": payload.knowledge_source_id if payload else None,
    }

    return {
        "content": content,
        "structured_metadata": metadata,
    }

    