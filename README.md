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
- employee management and face enrollment
- event ingest endpoint for the worker
- alert history and dashboard overview
- worker scaffold for webcam and DroidCam camera sources
- live camera preview for debugging the worker feed
- zone-aware event assignment with rule-based alerts
- face recognition that upgrades a detected `person` into a known `employee`

## Local Startup

### Fastest Dev Flow

Use the helper script from the repo root:

```powershell
cd F:\detection-ai
.\scripts\dev.ps1 start
```

Useful commands:

```powershell
.\scripts\dev.ps1 status
.\scripts\dev.ps1 verify
.\scripts\dev.ps1 stop
```

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

DroidCam direct stream on the same Wi-Fi:

```powershell
cd F:\detection-ai\apps\worker
(Get-Content .env) `
  -replace '^CAMERA_SOURCE_TYPE=.*$', 'CAMERA_SOURCE_TYPE=droidcam' `
  -replace '^CAMERA_SOURCE=.*$', 'CAMERA_SOURCE=http://YOUR_PHONE_IP:4747/video' `
  -replace '^DETECTOR_TYPE=.*$', 'DETECTOR_TYPE=yolo' |
Set-Content .env
python -m app.main
```

Recommended flow for DroidCam:

1. Open the DroidCam app on your phone.
2. Keep the phone and laptop on the same Wi-Fi.
3. Use the phone IP shown by DroidCam in `CAMERA_SOURCE`.
4. Open `http://127.0.0.1:5173/live` to confirm the worker sees the real feed.
5. Open `http://127.0.0.1:5173/alerts` to watch the saved alerts.

Before starting the worker for live ingest, create a site and camera in the dashboard and copy their IDs into:

- `SITE_ID`
- `CAMERA_ID`

### Employee Enrollment And Face Recognition

1. Start the stack with `.\scripts\dev.ps1 start`.
2. Open `http://127.0.0.1:5173` and log in as the admin.
3. Go to `Employees`.
4. Create the employee record first.
5. Upload one or more clear front-facing images for that employee.
6. Open `http://127.0.0.1:5173/live` and point the camera at that employee.

What happens next:

- the worker pulls enrolled employee images from the API
- it downloads the OpenCV face models automatically on first use
- it matches live faces against the enrolled profiles
- when a match is strong enough, the detection changes from `person` to `employee`
- that upgraded identity flows into the same rules and alerts pipeline

Tips for better recognition:

- use bright lighting
- keep the face mostly front-facing during enrollment
- upload more than one clear photo when possible
- keep `FACE_MATCH_THRESHOLD` conservative if you want fewer false matches

## Default Admin

- Email: `admin@example.com`
- Password: `Admin12345!`

Change these values in `apps/api/.env` before using the project beyond local development.

## Verification

Run the local checks:

```powershell
cd F:\detection-ai
.\scripts\dev.ps1 verify
```

This runs:

- Python compile checks
- API unit tests
- Worker unit tests
- Web lint
- Web production build

## Local Hostnames

For local development, `localhost` and `127.0.0.1` are both accepted by the API CORS config.

Examples:

- Web: `http://localhost:5173` or `http://127.0.0.1:5173`
- API: `http://localhost:8000` or `http://127.0.0.1:8000`
