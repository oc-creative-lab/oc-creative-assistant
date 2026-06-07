# oc-creative-assistant
OC Creative Assistant System

## Installing Dependencies

### Frontend Dependencies

Frontend dependencies are maintained in `frontend/package.json`. Enter the `frontend` directory and install them:

```powershell
cd frontend
npm install
```

Once the installation completes, you can return to the project root:

```powershell
cd ..
```

### Electron Dependencies

The Electron subproject is maintained in `electron/package.json`. Install its dependencies in the following order:

```powershell
cd electron
npm install
```

Afterwards, return to the project root:

```powershell
cd ..
```

### Backend Dependencies

We recommend first creating a Python virtual environment in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Backend dependencies are maintained in `backend/requirements.txt`. Install them after activating the virtual environment:

```powershell
pip install -r backend/requirements.txt
```

## Common Scripts

All of the following commands are run from the project root, i.e. the directory that contains the root `package.json`.

```powershell
npm run frontend:dev
```

Starts the frontend Vite dev server. This command enters the `frontend` subproject and runs `npm run dev`.

```powershell
npm run frontend:build
```

Builds the frontend artifacts. This command enters the `frontend` subproject and runs type checking and the Vite build.

```powershell
npm run backend:dev
```

Starts the backend FastAPI dev server, listening on `127.0.0.1:9000`. We recommend activating the Python virtual environment before running it.

```powershell
npm run backend:build
```

Runs the backend build script `scripts/build-backend.mjs`, which prepares the backend artifacts for the desktop packaging process.

```powershell
npm run electron:dev
```

Starts the Electron subproject in development mode. You must first complete the installation in the "Electron Dependencies" section above.

```powershell
npm run electron:build
```

Builds the Electron subproject. You must first complete the installation in the "Electron Dependencies" section above.

```powershell
npm run dev:desktop
```

Starts the desktop integrated development workflow, in which `scripts/dev-desktop.mjs` coordinates the frontend, backend, and Electron dev processes.

**Recommended**: First run `npm run frontend:dev` and `npm run backend:dev` in two separate terminals (the backend needs the virtual environment activated). Once Vite and FastAPI are ready, run `npm run dev:desktop`. The script reuses the already-running frontend and backend to avoid starting them twice; if they were not started manually, it will also spin up the frontend and backend automatically before opening Electron.

```powershell
npm run build:desktop
```

Runs the complete desktop build workflow, in which `scripts/build-desktop.mjs` coordinates the packaging steps for the frontend, backend, and Electron.
