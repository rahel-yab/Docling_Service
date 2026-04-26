# Docling service

This is a FastAPI service that fetches a PDF from a URL and converts it to markdown using Docling.

## Local run

1. Create and activate a virtual environment.
2. Install dependencies:

	pip install -r requirements.txt

3. Start the API:

	uvicorn app:app --reload --host 0.0.0.0 --port 8000

4. Verify health:

	curl http://localhost:8000/healthz

## Parse request formats

`POST /parse` accepts either:

1. JSON with `document_url` pointing to a PDF.
2. JSON with `file_base64` containing the PDF bytes.
3. `multipart/form-data` with an uploaded PDF in `document_file`, `file`, or `pdf`.

Example JSON:

	curl -X POST http://localhost:8000/parse \
	  -H "Content-Type: application/json" \
	  -d '{"document_url":"https://example.com/file.pdf"}'

Example base64 JSON:

	curl -X POST http://localhost:8000/parse \
	  -H "Content-Type: application/json" \
	  -d '{"file_base64":"JVBERi0xLjcK...","file_name":"file.pdf"}'

Example upload:

	curl -X POST http://localhost:8000/parse \
	  -F "document_file=@./file.pdf"

