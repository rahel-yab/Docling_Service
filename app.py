import base64
from binascii import Error as BinasciiError
from tempfile import NamedTemporaryFile
from typing import Optional, Any
from functools import lru_cache

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


class ParseRequest(BaseModel):
    document_url: Optional[str] = None
    file_base64: Optional[str] = None
    file_name: Optional[str] = None
    company_id: Optional[str] = None
    company_url: Optional[str] = None
    knowledge_source_id: Optional[str] = None


app = FastAPI(title="Docling Parser")


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
    uploaded_pdf: Any | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_pdf = form.get("document_file") or form.get("file") or form.get("pdf")

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

    if payload is None and uploaded_pdf is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either document_url, file_base64, or an uploaded PDF as document_file/file/pdf.",
        )

    if payload is not None and payload.document_url:
        try:
            response = requests.get(payload.document_url, timeout=30)
            response.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to fetch document URL: {exc}") from exc

        pdf_bytes = response.content
    elif payload is not None and payload.file_base64:
        try:
            pdf_bytes = base64.b64decode(payload.file_base64, validate=True)
        except (BinasciiError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 PDF payload: {exc}") from exc
    else:
        pdf_bytes = await uploaded_pdf.read()

    with NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
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

    