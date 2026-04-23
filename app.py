from tempfile import NamedTemporaryFile
from typing import Optional, Any
from functools import lru_cache

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class ParseRequest(BaseModel):
    document_url: str
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
def parse_document(payload: ParseRequest) -> dict[str, Any]:
    try:
        response = requests.get(payload.document_url, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch document URL: {exc}") from exc

    with NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(response.content)
        tmp.flush()
        try:
            result = get_converter().convert(tmp.name)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Docling conversion failed: {exc}") from exc

    content = result.document.export_to_markdown()
    metadata = {
        "source_url": payload.document_url,
        "company_id": payload.company_id,
        "company_url": payload.company_url,
        "knowledge_source_id": payload.knowledge_source_id,
    }

    return {
        "content": content,
        "structured_metadata": metadata,
    }

    