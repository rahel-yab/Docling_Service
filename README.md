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

## Deploy on Render

This repo includes a Render blueprint file: render.yaml.

1. Push this repository to GitHub.
2. In Render, click New + and select Blueprint.
3. Connect the GitHub repo and deploy.

Render will use:

- Build command: pip install -r requirements.txt
- Start command: uvicorn app:app --host 0.0.0.0 --port $PORT
- Health check: /healthz
- Python version: 3.11.9

## Test the deployed service

Replace YOUR_RENDER_URL with your Render service URL:

curl -X POST "https://YOUR_RENDER_URL/parse" \
  -H "Content-Type: application/json" \
  -d '{
	 "document_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
	 "company_id": "123",
	 "company_url": "https://example.com",
	 "knowledge_source_id": "abc"
  }'

## Notes

- Docling can be memory and CPU heavy. If deploys fail on low plans, use at least Starter.
- For large PDFs, increase request timeout on clients that call this API.
- If Render build logs show Python 3.14 and fail on python-bidi or maturin/Rust, keep Python pinned to 3.11 via .python-version (included in this repo).
