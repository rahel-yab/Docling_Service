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

