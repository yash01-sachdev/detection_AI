# Detection AI

Detection AI is a modular video intelligence platform built version by version for:

- object detection around homes, offices, and restaurants
- restricted-zone alerts
- employee recognition and presence tracking
- posture and inactivity monitoring
- configurable site modes with default rules

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy + JWT auth
- Worker: Python vision pipeline with pluggable camera sources
- Database: PostgreSQL in the target stack, with SQLite fallback for quick local startup
- Realtime: WebSocket-ready backend and Redis-ready infrastructure

## Monorepo Layout

```text
apps/
  api/       FastAPI backend
  web/       React admin dashboard
  worker/    Vision pipeline worker
infra/
  docker/    Local infrastructure services
storage/
  snapshots/ Saved event images
  clips/     Saved event clips
```

## V1 Scope

- admin login with JWT
- site mode selection: home, office, restaurant
- default rules per site mode
- site, camera, and zone management
- event ingest endpoint for the worker
- alert history and dashboard overview
- worker scaffold for webcam and DroidCam camera sources

## Local Startup

### 1. Infrastructure

Run PostgreSQL and Redis:

```powershell
cd F:\detection-ai\infra\docker
docker compose up -d
```

### 2. API

```powershell
cd F:\detection-ai\apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. Web

```powershell
cd F:\detection-ai\apps\web
npm install
Copy-Item .env.example .env
npm run dev
```

### 4. Worker

```powershell
cd F:\detection-ai\apps\worker
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.main
```

### Worker Camera Setup

Default local webcam:

```powershell
cd F:\detection-ai\apps\worker
(Get-Content .env) `
  -replace '^CAMERA_SOURCE_TYPE=.*$', 'CAMERA_SOURCE_TYPE=webcam' `
  -replace '^CAMERA_SOURCE=.*$', 'CAMERA_SOURCE=0' `
  -replace '^DETECTOR_TYPE=.*$', 'DETECTOR_TYPE=yolo' |
Set-Content .env
python -m app.main
```

DroidCam stream:

```powershell
cd F:\detection-ai\apps\worker
(Get-Content .env) `
  -replace '^CAMERA_SOURCE_TYPE=.*$', 'CAMERA_SOURCE_TYPE=droidcam' `
  -replace '^CAMERA_SOURCE=.*$', 'CAMERA_SOURCE=http://YOUR_PHONE_IP:4747/video' `
  -replace '^DETECTOR_TYPE=.*$', 'DETECTOR_TYPE=yolo' |
Set-Content .env
python -m app.main
```

Before starting the worker for live ingest, create a site and camera in the dashboard and copy their IDs into:

- `SITE_ID`
- `CAMERA_ID`

## Default Admin

- Email: `admin@example.com`
- Password: `Admin12345!`

Change these values in `apps/api/.env` before using the project beyond local development.
