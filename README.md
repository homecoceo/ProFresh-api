# Pro-Fresh Houston — PDF Report API

## What this is
A Flask API that accepts job data from the Pro-Fresh field form and generates a branded 2-page PDF post-service report.

## Files
- `app.py` — the main API server
- `requirements.txt` — Python dependencies
- `Procfile` — tells Render how to run the server
- `logo.png` — Pro-Fresh logo (place in same folder)

## Deploy to Render
1. Create a free account at render.com
2. New > Web Service
3. Connect your GitHub repo (upload these files first)
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Deploy

## API Endpoint
POST /generate-report
Content-Type: application/json

Returns: PDF file download

## Test it
GET /health — should return {"status": "ok"}
