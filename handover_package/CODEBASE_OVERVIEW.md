# Codebase Overview

**Project:** Artery Segmentation and Stenosis Detection System  
**Repository inspected:** `C:\Users\namde\artery-stenosis-project`  
**Handover prepared:** 2026-11-11 (Asia/Calcutta)

This document reflects the files present during this inspection. Earlier chat notes are useful project history, but the current repository takes precedence when the two disagree.

## Architecture

The application is a React single-page frontend served by Vite, with a separate FastAPI JSON API under `/api/v1`. FastAPI uses SQLAlchemy 2 sessions, PostgreSQL via Psycopg 3, and Alembic migrations. Uploaded image bytes are kept in local filesystem storage; image and preprocessing metadata are stored in PostgreSQL. The frontend reaches the API through Vite's `/api` development proxy and a shared fetch helper that attaches a bearer token.

The repository also has a separate `ml/` research/training package. It has training/evaluation scripts and local model artifacts, but no API inference adapter or application analysis pipeline currently loads these artifacts. Backend preprocessing is an independent, non-inference step.

## Technology and dependency manifests

| Area | Current stack / manifest |
|---|---|
| Frontend | React 19, TypeScript, React Router 7, Vite 8; `package.json`, `package-lock.json` |
| Backend API | Python, FastAPI, Uvicorn; `backend/requirements.txt` |
| Persistence | SQLAlchemy 2, Psycopg 3, PostgreSQL 16 (Compose image), Alembic |
| Validation/security | Pydantic Settings, email-validator, PyJWT, pwdlib with Argon2 |
| Image services | Pillow and NumPy in backend dependencies |
| ML training | PyTorch, NumPy, Pillow; there is no separate ML dependency manifest in the inspected tree. Backend requirements do not install PyTorch. |

## Repository map

```text
.
├── src/                         React UI, routes, auth, API-backed features
│   ├── auth/                    Auth provider, protected route, API helper, admin preview gate
│   ├── components/              Shared shell, navigation, notices, panels, empty states
│   ├── features/cases/           Case API hook, types, form dialog
│   ├── features/patients/        Patient API hook, types, form dialog
│   ├── pages/                    Login, dashboard, patients, cases, upload, results, reports, users, settings
│   ├── App.tsx                   Frontend routes
│   └── styles.css                Shared visual system and responsive styles
├── backend/
│   ├── app/api/v1/endpoints/     FastAPI endpoint modules
│   ├── app/api/deps.py           Authentication, role, ownership dependencies
│   ├── app/core/                 Settings and password/JWT security
│   ├── app/db/                   SQLAlchemy base and session dependencies
│   ├── app/models/               SQLAlchemy tables
│   ├── app/schemas/              Pydantic request/response types
│   ├── app/services/             Safe local image storage and preprocessing
│   ├── migrations/versions/      Initial schema and preprocessing metadata migration
│   ├── tests/                    API and image preprocessing tests
│   ├── storage/uploads/           Local uploaded image files (ignored/private)
│   ├── .env.example              Placeholder configuration only
│   ├── .postgres.env.example     Placeholder Compose database configuration only
│   ├── requirements.txt
│   └── README.md                 Setup/API documentation (some integration statements are stale; see below)
├── ml/                           Dataset/training/research code and local artifacts
│   ├── models/                   Baseline U-Net and Attention U-Net definitions
│   ├── tests/                    Dataset/training utility tests
│   ├── checkpoints/              Local Attention U-Net checkpoint (large; excluded from archives)
│   ├── performance-test/         Baseline smoke checkpoint (excluded from archives)
│   ├── reports/                  Training/evaluation records (not bundled as source)
│   └── task4..task6, geometry and training scripts
├── design-references/            Eight UI screenshots, including reference-only model screen
├── compose.yaml                  Local PostgreSQL service and persistent named volume
├── vite.config.ts                Vite and local `/api` proxy to 127.0.0.1:8000
├── package.json / package-lock.json
├── tsconfig*.json, index.html
├── .gitignore
└── outputs/                      Generated output (not source; excluded from handover archives)
```

`git status` could not be checked because this project folder does not contain a `.git` repository at inspection time. The source archives omit Git history in any case.

## Frontend routes, pages, and current behavior

`src/App.tsx` wraps application routes in `ProtectedRoute` and `AppShell`; `/login` is public. Unknown routes redirect to login. `/analysis` redirects to `/upload`.

| Route | Component | Current behavior |
|---|---|---|
| `/login` | `src/pages/LoginPage.tsx` | Authenticates against the API; password recovery and institutional sign-in are placeholders. |
| `/dashboard` | `DashboardPage.tsx` | UI is present, but summary metrics/activity are static zero/empty preview content. Case creation and view-all links go to Cases. |
| `/patients` | `PatientsPage.tsx` | Authenticated API-backed list/create/view/update of patient references; associated case counts come from the cases API. No demographic/clinical fields are modeled. |
| `/cases` | `CasesPage.tsx` | Authenticated API-backed list/create/view/update with patient association; actual image count is queried from image APIs. Image management itself stays in Upload. |
| `/upload` | `UploadAnalysisPage.tsx` | Selects an owned case, uploads PNG/JPG/JPEG files, loads saved image rows and protected previews, runs/reloads preprocessing status/results. Model analysis remains unavailable. Selected case is restored from session storage when it still appears in the authenticated case list. |
| `/analysis` | Route redirect | Redirects to `/upload`; no separate analysis page. |
| `/results` | `ResultsPage.tsx` | Layout/tabs only; selectors and output tools are disabled/empty because inference and results APIs are unavailable. |
| `/reports` | `ReportsPage.tsx` | Preview layout and local tab selection; report selection, generation, export, notes and report sections are disabled/placeholders. |
| `/users` | `UsersPage.tsx` | Frontend admin-only route, but the content is placeholder data/UI. Backend admin list/create APIs exist but this page does not call them. |
| `/settings` | `SettingsPage.tsx` | Shows authenticated profile/role and static access information; profile/preferences/notification toggles are not persisted. |

Shared shell/navigation are in `src/components/AppShell.tsx`, `Sidebar.tsx`, and `TopBar.tsx`. `src/features/{cases,patients}` contains API hooks and form components. Some notices still contain stale wording: `PreviewNotice.tsx` says patient management is unavailable even though PatientsPage is API-backed. The backend README likewise says the frontend is not wired, which no longer matches the current hooks and upload page.

## API routes

All routes below are prefixed with `/api/v1`. Authentication and ownership are enforced in route dependencies; for user-owned resources, non-admin users receive only their own rows. Missing/non-owned patient, case, and image IDs are generally concealed as 404.

| Method | Endpoint | Access | Purpose / actual status |
|---|---|---|---|
| `GET` | `/health` | Public | Executes `SELECT 1`; 200 when DB reachable, 503 otherwise. |
| `POST` | `/auth/login` | Public | Verifies active user's email/password and returns bearer JWT. |
| `GET` | `/auth/me` | Bearer | Returns current active user and role. |
| `GET` | `/users` | Admin | Lists user accounts. |
| `POST` | `/users` | Admin | Creates an administrator-managed account with hashed password. |
| `GET` | `/patients` | Bearer | Lists caller-owned patients; admin can list all. |
| `POST` | `/patients` | Bearer | Creates patient reference; non-admin cannot assign another owner. |
| `GET` | `/patients/{patient_id}` | Bearer | Reads owned patient or admin-accessible patient. |
| `PATCH` | `/patients/{patient_id}` | Bearer | Updates patient reference. |
| `GET` | `/cases` | Bearer | Lists caller-owned cases; admin can list all. |
| `POST` | `/cases` | Bearer | Creates a case against an accessible patient, using patient ownership. |
| `GET` | `/cases/{case_id}` | Bearer | Reads owned case or admin-accessible case. |
| `PATCH` | `/cases/{case_id}` | Bearer | Updates supported case fields (`case_ref`, nullable `modality`). Patient association is not changed. |
| `POST` | `/cases/{case_id}/images` | Bearer | Validates PNG/JPG/JPEG extension and actual content, size, pixels; stores bytes locally and metadata in DB. |
| `GET` | `/cases/{case_id}/images` | Bearer | Lists image metadata for accessible case. |
| `GET` | `/images/{image_id}/content` | Bearer | Streams original image only to owner/admin. |
| `POST` | `/images/{image_id}/preprocess` | Bearer | Runs reusable non-destructive preprocessing, then stores status/result metadata only. Not segmentation/inference. |
| `GET` | `/cases/{case_id}/preprocessing` | Bearer | Returns per-image `not_started`, `completed`, or `failed` state and saved metadata. |
| `POST` | `/cases/{case_id}/analysis-runs` | Bearer | Always reports 503 `analysis_unavailable`; does not enqueue work or create a run. |
| `GET` | `/analysis-runs/{run_id}` | Bearer | Existing run lookup is ownership-scoped; no worker creates runs. Existing record returns 503 unavailable; absent/inaccessible record is 404. |
| `GET` | `/analysis-runs/{run_id}/results` | Bearer | Existing run is scoped then returns 503 `results_unavailable`; no clinical findings are returned. |
| `GET` | `/notifications` | Bearer | Lists current user's notifications. No producer/persistence workflow for notifications is implemented. |

There is no report-generation API, no settings API, and no account update/password recovery API. There are no job queue, background worker, retry scheduler, or analysis-status lifecycle. Preprocessing attempts are synchronous and manually retryable; that is not a background job system.

## Database and migration shape

The ORM classes are in `backend/app/models/`; Alembic revisions currently present are `0001_initial_backend_schema.py` and `0002_image_preprocessing.py`.

| Table | Key stored information |
|---|---|
| `users` | UUID, unique email, Argon2 password hash, role (`admin`/`user`), active flag, creation time. |
| `patients` | UUID, owner user, patient reference, creation time; unique `(owner_id, patient_ref)`. |
| `cases` | UUID, owner, patient, case reference, nullable modality, creation time; unique `(owner_id, case_ref)`. |
| `medical_images` | UUID, case and uploader, generated storage key, original filename metadata, media type, byte size, SHA-256, created time. Pixel bytes are not stored in this table. |
| `image_preprocessing` | One latest attempt per image: actor, status, attempt count, JSON result metadata/failure message, updated time. No transformed pixel arrays are stored. |
| `analysis_runs` | Reserved schema for future run metadata; current API does not create runs or execute them. |
| `notifications` | User-scoped notification rows; current API only lists rows and has no producer. |

Relationships are represented by foreign keys, with cascading deletion configured in the models. Do not reset or recreate the database for normal development.

## Authentication, authorization, and frontend API calls

Backend `POST /auth/login` normalizes email to lowercase, verifies the Argon2 password hash, rejects inactive accounts, and signs an HS256 JWT with subject=user UUID and configured expiry. `get_current_user` validates the bearer token and resolves an active DB user. `require_admin` enforces administrator access. Ownership helpers scope patient/case/image queries to `owner_id`; an ID alone grants no access.

Frontend `src/auth/AuthProvider.tsx` obtains a token from `localStorage` key `access_token`, calls `/auth/me` on startup, submits login and then loads `/auth/me`, and clears the token on logout or unauthorized response. `src/auth/api.ts` prepends `/api/v1`, adds `Authorization: Bearer ...` except login, uses JSON or `FormData` appropriately, dispatches `auth:unauthorized` on 401, and has a bearer-aware blob helper for image previews. `ProtectedRoute.tsx` blocks protected routes until session checking completes and redirects unauthenticated users to `/login`.

The token is stored in browser local storage, so it is accessible to JavaScript on the origin; this is the implemented architecture, not an HttpOnly-cookie design. Keep session handling consistent if security architecture changes later.

## Image upload and preprocessing lifecycle

1. Frontend loads authenticated cases/patients and restores the last case from `sessionStorage` key `artery-image-upload-selected-case` only if it is still in the user's fetched case list.
2. On case selection, it fetches `/cases/{id}/images` and `/cases/{id}/preprocessing`; previews are fetched from the protected content API with the bearer token.
3. File selection checks extension in the browser. Server validation is authoritative: only `.png`, `.jpg`, `.jpeg`; the decoded Pillow format must agree with extension; byte cap defaults to 10 MiB (configurable up to 100 MiB), pixel cap defaults to 40 million (configurable up to 100 million). Generated UUID names are stored under `UPLOAD_DIRECTORY`, and original name is metadata only. Path resolution is guarded against traversal.
4. Upload creates `medical_images` metadata after file storage; on DB failure the just-written file is removed.
5. Preprocessing is a separate explicit action. It revalidates stored file content and size, converts supported image representations to one grayscale channel, scales unsigned intensity range to `[0,1]` without per-image contrast stretch, fits by Lanczos while preserving aspect ratio, zero-pads to configured 256×256, and produces contiguous NumPy `float32` CHW shape `[1,H,W]`. It never mutates the original and discards pixel output after the synchronous request.
6. A successful preprocessing record is persisted only after processing returns successfully. Failure status/message and attempt count are persisted to permit retry. API and UI explicitly state this is not segmentation or clinical analysis.

## ML/training state (separate from application inference)

`ml/dataset.py` reads the ARCADE `syntax` train/val/test layout, pairs images and prepared masks by filename stem, converts images to grayscale and masks to binary in memory, and leaves the dataset unchanged. `ml/train_baseline.py` trains the existing baseline U-Net with BCE+Dice and selects checkpoints on validation Dice; its code does not use test for selection. `ml/models/attention_unet.py` and `ml/train_attention_unet.py` define/train an Attention U-Net. `ml/task4_generate_artery_masks.py`, `task5_segmentation_postprocessing.py`, `task6_vessel_structure_extraction.py`, and geometry scripts are research/standalone pipeline work, not connected to the FastAPI analysis API.

Current local artifacts inspected:

- `ml/checkpoints/best_attention_unet.pt` exists (about 377 MB). Its saved report records a 30-epoch Attention U-Net run, best validation Dice `0.8052` at epoch 12, then a saved test report with 300 test images and Dice `0.7597`. These are repository report values, not clinical validation, and were not independently recomputed during this handover.
- `ml/performance-test/checkpoints/best_unet.pt` exists (about 124 MB). Its smoke report records one epoch with four training and two validation samples at 128×128 and validation Dice about `0.0020`. The prior chat investigation found metric/preprocessing were consistent with the code and the poor score was due to nearly empty, untrained smoke predictions.
- `ml/reports/baseline_training_report.json` records a separate 30-epoch CUDA baseline run with best validation Dice `0.7971` at epoch 13 and says its checkpoint path was `/kaggle/working/unet_full_training/checkpoints/best_unet.pt`; that baseline checkpoint is not present in the local `ml/checkpoints` folder. The report's previously reported baseline test score is not independently re-evaluated in the comparison file.
- The backend never loads either local checkpoint. `/analysis-runs` remains unavailable; no predictions, measurements, stenosis findings, or generated reports are produced by the application.

The dataset and prepared masks used in training are referenced outside the project (`C:\Users\namde\Downloads\arcade\...` in the baseline README); they are not included in handover archives. Full training dependencies are not separately pinned in this repository.

## Configuration and secrets

Configuration is read by `backend/app/core/config.py` from `backend/.env` (and process environment). Names present in `backend/.env.example` are:

The example file lists `ENVIRONMENT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `CORS_ORIGINS`, `MAX_UPLOAD_SIZE_BYTES`, `MAX_IMAGE_PIXELS`, and `UPLOAD_DIRECTORY`. `DATABASE_URL` is an optional override supported by the settings class but is not present in the example file. Compose reads `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` from `backend/.postgres.env`.

Compose reads database settings from `backend/.postgres.env`; its names are `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`. Actual `.env` and `.postgres.env` files are private and excluded from source archives. Never copy their values into documentation or chat. The checked-in example files contain placeholders only. Signing key must be at least 32 bytes at runtime. The local Vite proxy target is `http://127.0.0.1:8000`; default allowed browser origins are localhost and 127.0.0.1 at port 5173.

## Local setup and execution

Prerequisites: Node.js/npm, Python compatible with the installed/pinned-by-range requirements, Docker Desktop with Compose (or a separately configured PostgreSQL instance), and the external ARCADE data only for ML training.

PowerShell commands from the repository root (follow `backend/README.md` for creating private config and setting local credentials; do not use example placeholders as real credentials):

```powershell
# Configure backend/.env and backend/.postgres.env from the example files first.
docker compose up -d db
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.cli create-admin --email admin@example.local
uvicorn app.main:app --reload
```

In another terminal at project root:

```powershell
npm ci
npm run dev
```

Frontend: `http://localhost:5173`; API: `http://127.0.0.1:8000`; docs: `http://127.0.0.1:8000/docs`; DB-backed health: `http://127.0.0.1:8000/api/v1/health`. The `/api` Vite proxy forwards to the API. `npm ci` and `pip install` are setup instructions only; they were not run while preparing this handover.

Backend tests from repository root: `python -B -m pytest -q -p no:cacheprovider backend/tests`. ML unit tests: `python -B -m pytest -q -p no:cacheprovider ml/tests`. ML baseline train command and CPU smoke options are in `ml/README.md`; full train requires local dataset paths and PyTorch.

## Implemented, limited, and unverified

**Present in current code:** authenticated login/session, current user and role, admin account list/create endpoints, patient and case CRUD APIs and UI, protected image upload/list/content and UI, persisted preprocessing metadata and UI, PostgreSQL config/migrations, DB health endpoint, separate ML training scripts and local Attention U-Net artifact/reports.

**Not implemented in the application:** model inference, analysis job queue/background jobs, automatic retries, analysis run creation/status persistence, segmentation/stenosis clinical measurements, results API, report generation/export API, persisted preferences, password recovery, user-management frontend/API edit/deactivate workflows, notification producer.

**Not verified by this handover:** live PostgreSQL migration execution, browser login/upload/preprocess workflow, model artifact loading, reproducibility of historical report metrics, actual external dataset availability, CUDA environment. The Python test invocation was attempted but did not return a test summary before the process session ceased to be observable; therefore this handover does not claim those tests passed. The frontend production build was not rerun to avoid regenerating the existing `dist/` output. Previously reported checks in chat are historical and should be rerun before relying on them.

Potential code/documentation issues to review:

- `backend/README.md` has an obsolete opening claim that the frontend is not wired to the API.
- `src/components/PreviewNotice.tsx` claims patient management is unavailable although the current Patients page uses authenticated APIs.
- Dashboard metrics and activity remain static zero/empty content, not live API aggregates.
- `UsersPage.tsx` is placeholder UI despite working admin list/create endpoints. Some copy still says authentication is not connected despite current auth.
- Results, reports, settings persistence, notification generation, and actual analysis remain unimplemented.
- No root-level or ML-specific dependency manifest exists; backend requirements do not pin PyTorch.
- No `.git` directory was present, so branch and uncommitted-change status could not be determined.

## First files to inspect before any future changes

1. `src/App.tsx`, `src/auth/api.ts`, `src/auth/AuthProvider.tsx`, `src/auth/ProtectedRoute.tsx` for route/session behavior.
2. `src/pages/UploadAnalysisPage.tsx`, `src/features/cases/useCases.ts`, `src/features/patients/usePatients.ts` for existing frontend API workflows.
3. `backend/app/api/deps.py` and endpoint files for authorization and behavior.
4. `backend/app/models/`, `backend/app/schemas/`, and `backend/migrations/versions/` before altering data contracts.
5. `backend/app/services/storage.py` and `preprocessing.py` before touching image paths/pixels.
6. `ml/dataset.py`, `ml/train_baseline.py`, `ml/models/`, plus `ml/README.md` before ML changes. Treat reports and checkpoints as artifacts; do not assume they are application inference wiring.
7. `backend/README.md`, `backend/.env.example`, `.gitignore`, `compose.yaml`, `vite.config.ts` for local setup and safe configuration.

## Archive contents and exclusions

`artery-frontend-source.zip` includes frontend source, package manifests/config, and UI reference images. `artery-backend-source.zip` includes FastAPI source, migrations, tests, manifests/examples, Compose/ignore config, and ML Python source/tests/docs. Both exclude `.git`, actual `.env` files, credentials, uploaded data, datasets, model weights/checkpoints, generated reports/output, caches, `node_modules`, Python environments, and Vite build output. The source ZIPs are not runtime-complete for ML inference: no inference integration exists, and training dataset/weight files are intentionally omitted.
