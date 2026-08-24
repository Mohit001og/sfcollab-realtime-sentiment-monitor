# SFCollab Real-Time Sentiment Monitor

SFCollab is an incremental demo project for monitoring team-chat sentiment in real time. It scores submitted messages, broadcasts processed events to connected dashboards, and maintains a rolling 60-minute team mood summary.

## Architecture

- Frontend: React + Vite dashboard with a live message feed, current mood card, and SVG 60-minute mood chart.
- Backend: FastAPI application served by Uvicorn.
- Sentiment engine: lightweight Hugging Face text-classification model loaded lazily and cached per backend process.
- Real-time delivery: FastAPI WebSocket endpoint at `/ws`.
- Rolling mood: in-memory 60-minute window using signed sentiment confidence values.

## Local Backend Setup

Use Python 3.13.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

## Local Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

By default, the frontend uses:

- HTTP backend URL: `http://127.0.0.1:8000`
- WebSocket backend URL: `ws://127.0.0.1:8000/ws`

## Environment Variables

Frontend variables are public at build time. Do not put secrets in `VITE_*` values.

- `VITE_BACKEND_HTTP_URL`: backend HTTP base URL, for example `https://example-backend.com`
- `VITE_BACKEND_WS_URL`: backend WebSocket URL, for example `wss://example-backend.com/ws`

Backend:

- `FRONTEND_ORIGINS`: comma-separated browser origins allowed by CORS.

Example:

```powershell
$env:FRONTEND_ORIGINS = "http://localhost:5173,https://example-frontend.com"
```

## Production

Backend start command:

```powershell
cd backend
python -m app.server
```

`app.server` reads the deployment-provided `PORT` environment variable and defaults to `8000` locally. The direct Uvicorn command also remains valid:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend build:

```powershell
cd frontend
npm run build
```

Deploy `frontend/dist` with a static hosting service. The deployed frontend must be built with backend HTTP and WebSocket URLs that match the deployed backend. The backend must include the deployed frontend origin in `FRONTEND_ORIGINS`.

## Demo Stream

The demo stream posts realistic team-chat messages to the backend and reports real model responses.

```powershell
python scripts\demo_stream.py
python scripts\demo_stream.py --url http://127.0.0.1:8000 --delay 2
```

## Testing

Backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

From the repository root, this equivalent command is often simpler:

```powershell
.venv\Scripts\python.exe -m pytest backend -q
```

Frontend:

```powershell
cd frontend
npm run build
```

Diff hygiene:

```powershell
git diff --check
```

The backend test suite currently passes with one known `StarletteDeprecationWarning` from `fastapi.testclient` about `httpx` / `httpx2`.

## Known Limitations

- Rolling mood state is in memory and intended for a single backend process/demo deployment.
- Restarting the backend clears the active rolling mood history.
- Authentication, database persistence, and distributed pub/sub are intentionally out of scope for this incremental demo.
