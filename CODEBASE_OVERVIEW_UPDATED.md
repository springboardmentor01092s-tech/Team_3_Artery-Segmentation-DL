# Artery Analysis System — Updated Codebase Overview

**Repository:** `C:\Users\namde\artery-stenosis-project`  
**Purpose:** Technical reference for the current source tree. This is a research/workspace application; it does not provide clinically validated findings.

## Evidence and status labels

- **Implemented in source** means the current files contain the described implementation; it does not by itself prove live service behavior.
- **Automated check recorded** means a command in the current Codex conversation returned a result.
- **User-reported browser behavior** means the user reported seeing it in a running application; it was not rechecked during this documentation task.
- **Unverified** means runtime, database state, or behavior was not checked here.

No credentials, `.env` contents, access tokens, uploaded images, or patient records were inspected for these documents.

## Architecture and stack

The project is a React/Vite browser application backed by a separate FastAPI service and PostgreSQL. The Vite development server proxies `/api` to `http://127.0.0.1:8000` (`vite.config.ts`). The backend mounts its routers under `/api/v1` (`backend/app/main.py`, `backend/app/api/v1/router.py`). Frontend calls use `src/auth/api.ts`, which adds the `/api/v1` prefix and bearer token.

| Layer | Current implementation |
|---|---|
| Frontend | React 19, TypeScript, Vite 8, React Router 7, Lucide icons; `package.json` |
| Backend | Python 3.10 project, FastAPI, SQLAlchemy 2, Psycopg 3, Alembic, Pydantic Settings; `backend/requirements.txt` |
| Database | PostgreSQL 16 container for local development; PostgreSQL via SQLAlchemy/Psycopg; `compose.yaml`, `backend/app/db/session.py` |
| ML runtime | Separate CPU-oriented Python environment described by `ml/requirements-inference.txt`; API starts a private, persistent ML worker lazily through `backend/app/services/analysis_inference.py` |
| Tests | Node built-in test runner for frontend `.mjs` helpers and pytest for backend/ML code |

### Main directories

| Path | Purpose |
|---|---|
| `src/auth/` | Login context, bearer-token API helpers, route guards and preview-role gate |
| `src/components/` | Shared app shell, sidebar, top bar, panels, cards and empty states |
| `src/features/` | Feature-specific cases, patients, dashboard aggregation, notifications, analysis and report utilities |
| `src/pages/` | Login, Dashboard, Patients, Cases, Upload & Analysis, Results, Reports, Users and Settings screens |
| `backend/app/api/v1/endpoints/` | Versioned FastAPI endpoints |
| `backend/app/models/`, `schemas/` | SQLAlchemy tables and Pydantic request/response contracts |
| `backend/app/services/` | Local image storage, preprocessing, inference bridge, artifact storage and severity assessment |
| `backend/migrations/versions/` | Alembic revisions `0001`, `0002`, and `0003` |
| `backend/tests/` | Backend API, image preprocessing, analysis and severity tests |
| `ml/models/` | Attention U-Net and baseline U-Net architectures |
| `ml/inference/` | Attention U-Net and U-Net++ adapters, combined pipeline, candidate extraction, percentage narrowing, worker and run CLI |
| `ml/tests/` | Model adapter, Grad-CAM, pipeline, training-data and percentage-narrowing tests |
| `ml/checkpoints/` | Repository-local Attention U-Net checkpoint; do not include checkpoints in source archives |
| `design-references/`, `research_reference/` | UI reference and research/prototype material |
| `tests/` | Frontend Node test files |

Generated/dependency directories such as `node_modules/`, `dist/`, virtual environments, caches, `backend/storage/`, uploaded images and analysis output are not source documentation. The backend `.env` and `.postgres.env` are private files and were not read.

## Frontend routes and authentication flow

Routes are declared in `src/App.tsx`:

| Route | Page / behavior | Access |
|---|---|---|
| `/login` | `src/pages/LoginPage.tsx` | Public |
| `/dashboard` | `src/pages/DashboardPage.tsx` | Protected |
| `/patients` | `src/pages/PatientsPage.tsx` | Protected |
| `/cases` | `src/pages/CasesPage.tsx` | Protected |
| `/upload` | `src/pages/UploadAnalysisPage.tsx` | Protected |
| `/analysis` | Redirects to `/upload` | Protected |
| `/results` | `src/pages/ResultsPage.tsx` | Protected |
| `/reports` | `src/pages/ReportsPage.tsx` | Protected |
| `/users` | `src/pages/UsersPage.tsx` | Protected and frontend-gated to admin preview |
| `/settings` | `src/pages/SettingsPage.tsx` | Protected |

`src/auth/AuthProvider.tsx` posts credentials to `/auth/login`, stores the returned bearer token in `localStorage`, then loads `/auth/me`. On refresh it restores the user from `/auth/me`. `ProtectedRoute.tsx` redirects a missing/expired session to login. A 401 from `apiRequest` or `apiRequestBlob` clears the token and dispatches `auth:unauthorized`. Login currently replaces the route with `/dashboard`; logout clears the token and returns to login. Backend role/ownership enforcement is authoritative; the `/users` frontend gate is only a UI layer.

Passwords are hashed using `pwdlib`'s recommended Argon2 configuration (`backend/app/core/security.py`). JWTs use PyJWT/HS256 and a configured signing secret. There is no public registration or password-recovery endpoint. The initial administrator is created using `python -m app.cli create-admin --email <email>` from `backend/`; later accounts use the admin-only users API.

## Database and authorization

SQLAlchemy models are in `backend/app/models/`. Foreign keys and uniqueness constraints define the data relations; ORM `relationship()` declarations are not used in the inspected models.

| Table | Important fields / relationships |
|---|---|
| `users` | Email, password hash, role (`admin`/`user`), active flag, creation time |
| `patients` | `owner_id → users.id`, patient reference; unique `(owner_id, patient_ref)` |
| `cases` | `owner_id → users.id`, `patient_id → patients.id`, case reference, modality; unique `(owner_id, case_ref)` |
| `medical_images` | `case_id → cases.id`, `uploaded_by_id → users.id`, safe storage key, original filename metadata, media type, size, SHA-256, timestamp |
| `image_preprocessing` | One latest record per image (`image_id → medical_images.id`), actor, status, attempts, metadata JSON and failure message |
| `analysis_runs` | Case, optional source image, requester, status/timestamps/duration, result metadata JSON and failure fields |
| `notifications` | `user_id → users.id`, message, kind, timestamp |

`owned_or_admin` and endpoint-specific queries enforce tenant access. Non-admin users see records belonging to their cases/patients. Admins can access all; unauthorized or absent objects generally return 404. Image content and analysis artifacts are protected endpoints, not static public files.

Migration source files currently present: `backend/migrations/versions/0001_initial_backend_schema.py`, `0002_image_preprocessing.py`, `0003_analysis_run_results.py`. **The migration files exist; the currently running database revision was not queried in this documentation task.** The user previously reported revision 0003 applied, but that live state is not independently verified here.

## Patient, case and image workflow

1. Authenticated patient listing/creation/update uses `/patients` endpoints. `PatientsPage.tsx` and `src/features/patients/usePatients.ts` consume the API.
2. Cases reference a patient. `CasesPage.tsx` uses `src/features/cases/useCases.ts` and the case CRUD endpoints. It loads images and case-scoped analysis runs for visible/selected cases; analysis status aggregates all runs in the case with completed > active > failed > unavailable precedence.
3. Upload accepts PNG, JPG and JPEG. `backend/app/services/storage.py` checks both extension and decoded format/content, enforces byte and pixel caps, and stores bytes using a server-generated key. PostgreSQL stores metadata; files remain local under the configured upload directory.
4. The Cases page shows up to six image thumbnails. It uses the authenticated image-content endpoint and `object-fit: contain`; object URLs are revoked when the selection changes/unmounts.
5. Upload & Analysis page lists case images, supports local selection/preview, uploads to the selected case, loads persisted image records and preprocessing status, and invokes preprocessing only through its explicit action. The preprocess service is separate from segmentation inference.

Default backend upload limits are 10 MiB and 40 million decoded pixels, configurable within bounds (`backend/app/core/config.py`). PNG/JPG/JPEG are initially accepted. The exact runtime values can be overridden by environment; actual `.env` values were not inspected.

### Preprocessing

`POST /api/v1/images/{image_id}/preprocess` reads the existing stored image through the storage safety helper, validates it, converts it to grayscale, fits it to 256×256 while preserving aspect ratio, centers it with zero padding, and maps the unsigned source range linearly to float32 `[0,1]`. Output is one channel, CHW `[1,256,256]`; the array is returned in service memory and discarded. Only status, attempt count, actor and metadata are saved. The original file is not overwritten. `GET /api/v1/cases/{case_id}/preprocessing` lists each image's `not_started`, `completed` or `failed` status and metadata. This endpoint does **not** segment or analyze the image.

## AI inference and artifacts

### Two model adapters

`ml/inference/pipeline.py` runs both adapters independently from the original image argument. It does not feed one model's mask into the other model.

| Model | Current source contract |
|---|---|
| Artery segmentation | `ml/models/attention_unet.py`, `ml/inference/attention_unet.py`; grayscale 256×256, float32 `/255`, one-channel logits, sigmoid and threshold 0.50. `ml/checkpoints/best_attention_unet.pt` is present in the repository. This mask reflects the training target annotation; there is no evidence that it is a clinically defined lumen boundary. |
| Stenosis-candidate segmentation | `ml/inference/unetpp.py`; `segmentation_models_pytorch.UnetPlusPlus(encoder_name="resnet34", encoder_weights=None, in_channels=1, classes=1, activation=None)`. Grayscale 512×512, float32 `/255`, then `(x - 0.449) / 0.226`; sigmoid and provisional/configurable threshold default 0.20. The selected U-Net++ checkpoint is referenced outside the repository by the adapter's default and can also be set through backend configuration. Its current external-file availability was not checked here. |

The isolated ML environment is specified in `ml/requirements-inference.txt` (CPU torch/torchvision and SMP pins). The backend environment does not import PyTorch/SMP for inference. Configuration exposes `ML_PYTHON_EXECUTABLE`, `ATTENTION_CHECKPOINT_PATH`, `UNETPP_CHECKPOINT_PATH`, `ANALYSIS_STENOSIS_THRESHOLD`, `ANALYSIS_MIN_COMPONENT_AREA`, `ANALYSIS_CPU_THREADS`, timeouts and response-size bounds. Actual configured values/path existence are **unverified** because `.env` was not read.

### Candidate extraction, measurements and Grad-CAM

- `extract_candidates()` in `ml/inference/pipeline.py` extracts 8-connected regions from the stenosis mask on the U-Net++ model grid; default minimum area is 5 model-grid pixels. Candidate bounding boxes/centroids are transformed to original-image coordinates for aligned overlays and saved result metadata. Labels remain **predicted stenosis candidates**, not confirmed stenoses.
- `ml/inference/percentage_narrowing.py` estimates candidate-specific widths from aligned predicted artery and stenosis masks. It associates each candidate with a stenosis connected component and a dominant artery component, then measures predicted-mask widths along a skeleton using a distance transform. Output is in original-image pixels, not calibrated physical units or lumen diameter. Ambiguous cases are marked unavailable. The percentage is experimental and not clinically calibrated.
- `backend/app/services/severity_assessment.py` maps saved available narrowing percentages through user-specified project thresholds: Normal 0–25 inclusive; Mild >25 and <50; Moderate ≥50 and <70; Critical 70–100 inclusive. **No Severe category is implemented.** Thresholds are experimental, not clinically validated or independently approved. Missing/ambiguous narrowing remains unavailable and is not classified.
- U-Net++ adapter contains segmentation-targeted Grad-CAM using decoder layer `decoder.blocks.x_0_4.conv2.2`. It is optional: failures leave segmentation artifacts intact and report Grad-CAM unavailable. The raw backend `gradcam.png` is a grayscale heatmap. `src/features/analysis/gradcam-overlay.mjs` creates a display-only JET-colored blend (0.45 opacity) over the protected original source image; source artifacts are not rewritten. Results viewer and PDF use this client-side overlay. The label states that it is a model explanation, not a confirmed stenosis boundary.

### Backend inference lifecycle

`POST /api/v1/cases/{case_id}/analysis-runs` persists a run and performs inference synchronously. `InferenceWorker` in `backend/app/services/analysis_inference.py` starts a private loopback worker in the isolated ML Python environment, passes a per-process random internal token and a restricted environment, and reuses the resident model worker. A per-run CLI invocation returns arrays/artifacts; backend validation checks response metadata, masks, finite probabilities, dimensions, artifact allowlist and path containment. The original image stays in local upload storage. PostgreSQL stores run status and JSON metadata/relative artifact keys; model pixels are kept in files under private analysis storage, not exposed as public static files.

The run can be `processing`, `completed` or `failed` through the synchronous request; the schema also recognizes `queued` and `unavailable`, but no background queue is present. There is no automatic retry worker. A user can explicitly start another analysis request. No clinical validation is performed.

Artifacts currently supported by the result contract include original image URL, artery mask, stenosis mask, candidate overlay, combined visualization, optional Grad-CAM and candidate JSON. The combined visualization artifact-serving route includes an in-memory compatibility repair for legacy images. Results UI uses authenticated blob requests for protected artifacts, run selection, zoom/pan and fit/reset controls. The ruler remains unavailable because no calibrated physical measurement implementation is present. Only artifacts present in the response are displayed.

## Dashboard, Cases, Reports and Notifications

- **Dashboard** (`src/pages/DashboardPage.tsx`, `src/features/dashboard/dashboard-data.mjs`) fetches authenticated cases and patients, then case-scoped images and analysis runs with bounded concurrency. It calculates case/image/run summary counts, case-level status precedence, and recent case/image/run activity from real timestamps. Recent cases include patient references; recent runs include associated case/image IDs. An API error renders an error state instead of fabricated zero counts. No dedicated aggregate/activity API exists.
- **Cases** (`src/pages/CasesPage.tsx`) shows real image counts, run-derived case status, and up to six authenticated image previews. It uses `src/features/cases/case-preview.mjs` and authenticated APIs; content failures get per-image error presentation.
- **Reports** (`src/pages/ReportsPage.tsx`) selects patient, case, image and run from actual records. Selection IDs are stored in user-scoped `sessionStorage` and revalidated after reload; note text is deliberately not stored. PDF is generated in `src/features/reports/pdf-report.mjs`, including patient/case/image/run summary, candidate findings, Grad-CAM overlay and candidate localization when returned, plus Report Notes. It paginates when candidate/notes content requires it. JSON and CSV are generated client-side from saved run data (`report-exports.mjs`); CSV quotes comma/quote/newline fields and emits headers with no candidates. Protected artifacts are fetched using bearer-authenticated helpers. Model configuration remains in JSON analysis metadata, not in the current PDF section.
- **Notifications:** `src/features/notifications/NotificationProvider.tsx` currently holds report-export notifications in memory only. Opening the TopBar bell marks current notices read; a later notice is unread. The red dot is derived from unread count. This state disappears on reload. A backend `notifications` table and authenticated `GET /notifications` endpoint exist, but the current top-bar report notifications are not loaded from that endpoint. Backend has no create or mark-read endpoint, so backend notification persistence/read state is not integrated.
- **Users:** backend GET/POST `/users` is admin-only, but `src/pages/UsersPage.tsx` is still an admin-preview placeholder with static empty UI and disabled management actions; it does not call the users API.
- **Settings:** account role is shown from `/auth/me`; profile editing, notification preferences and display preferences are disabled/frontend-only. No settings persistence API was found.

## API inventory

All endpoints are under `/api/v1`. “Authenticated” routes require bearer authentication; ownership/admin scope is enforced on relevant records.

| Method | Endpoint | Purpose / access |
|---|---|---|
| GET | `/health` | Database-backed health check; public |
| POST | `/auth/login` | Email/password login; public |
| GET | `/auth/me` | Current account and role; authenticated |
| GET, POST | `/users` | List/create accounts; admin only |
| GET, POST | `/patients` | List/create patients; authenticated/owner scoped, admin can access all |
| GET, PATCH | `/patients/{patient_id}` | Read/update patient; authenticated/owner scoped |
| GET, POST | `/cases` | List/create cases; authenticated/owner scoped |
| GET, PATCH | `/cases/{case_id}` | Read/update case; authenticated/owner scoped |
| POST | `/cases/{case_id}/images` | Validate/store image and create metadata; authenticated/owner scoped |
| GET | `/cases/{case_id}/images` | List case image records; authenticated/owner scoped |
| GET | `/images/{image_id}/content` | Stream original image; authenticated/owner or admin |
| POST | `/images/{image_id}/preprocess` | Run initial preprocessing and persist status/metadata; authenticated/owner or admin |
| GET | `/cases/{case_id}/preprocessing` | List image preprocessing status for case; authenticated/owner or admin |
| POST | `/cases/{case_id}/analysis-runs` | Create persisted run and synchronously run the two-model pipeline; authenticated/owner or admin |
| GET | `/cases/{case_id}/analysis-runs` | List persisted runs for a case; authenticated/owner or admin |
| GET | `/analysis-runs/{run_id}` | Read run record/status; authenticated/owner or admin |
| GET | `/analysis-runs/{run_id}/results` | Read status and completed metadata/artifact URLs; authenticated/owner or admin |
| GET | `/analysis-runs/{run_id}/artifacts/{artifact_name}` | Stream allowlisted run artifact; authenticated/owner or admin |
| GET | `/notifications` | Read current user's DB notification records; authenticated |

No API endpoint was found for password recovery, user deletion, report storage, settings, database-backed report-notification creation/read acknowledgement, or aggregate dashboard data.

## Environment and local execution

`backend/app/core/config.py` reads `backend/.env` through Pydantic Settings. Variable names (not values):

`ENVIRONMENT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_HOST`, `DB_PORT`, `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `CORS_ORIGINS`, `MAX_UPLOAD_SIZE_BYTES`, `MAX_IMAGE_PIXELS`, `UPLOAD_DIRECTORY`, `ANALYSIS_OUTPUT_DIRECTORY`, `ATTENTION_CHECKPOINT_PATH`, `UNETPP_CHECKPOINT_PATH`, `ANALYSIS_STENOSIS_THRESHOLD`, `ANALYSIS_MIN_COMPONENT_AREA`, `ANALYSIS_CPU_THREADS`, `ML_PYTHON_EXECUTABLE`, `ANALYSIS_TIMEOUT_SECONDS`, `ANALYSIS_WORKER_STARTUP_TIMEOUT_SECONDS`, `ANALYSIS_MAX_RESPONSE_BYTES`.

The checked-in `backend/.env.example` and `backend/.postgres.env.example` are templates; actual `.env` values were not inspected. CORS defaults include local Vite origins. Do not commit actual env files or image/checkpoint data.

Typical PowerShell local startup, following `backend/README.md` with current source routes:

1. From project root, configure private env files from their examples and ensure Docker Desktop is available; start PostgreSQL with `docker compose up -d db`.
2. Backend terminal: `cd backend`; activate the existing `.venv` (`.\.venv\Scripts\Activate.ps1`); run `alembic upgrade head`; then `uvicorn app.main:app --reload` (or `python -m uvicorn app.main:app --reload`). Initial admin command: `python -m app.cli create-admin --email <admin-email>`.
3. Frontend terminal at project root: `npm run dev`; Vite serves the app on its configured local origin and proxies `/api` to port 8000.
4. For real inference, configure and install the separate `ml/.venv` using `ml/requirements-inference.txt`, set the ML executable and both checkpoint settings, and ensure referenced artifacts exist. This configuration/runtime was not checked here.

Backend settings require PostgreSQL credentials and a signing key of at least 32 bytes. Do not expose or paste those values into logs or reports.

## Tests and verification evidence

Current test files include:

- Frontend: `tests/analysis-contracts.test.mjs`, `auth-redirect.test.mjs`, `case-dashboard-integration.test.mjs`, `dashboard-data.test.mjs`, `gradcam-overlay.test.mjs`, `notification-state.test.mjs`, `report-export-ui.test.mjs`, `report-pdf.test.mjs`, `report-selection.test.mjs`, `results-summary-panels.test.mjs`, `viewer-controls.test.mjs`.
- Backend: `backend/tests/test_api.py`, `test_analysis.py`, `test_preprocessing.py`, `test_severity_assessment.py`.
- ML: `ml/tests/test_attention_checkpoint_smoke.py`, `test_attention_inference.py`, `test_dataset_training.py`, `test_gradcam_worker_bridge.py`, `test_inference_pipeline.py`, `test_percentage_narrowing.py`, `test_unetpp_gradcam.py`, `test_unetpp_inference.py`.

**Latest recorded automated frontend result in this Codex conversation:** `npm test` passed 43/43 tests and `npm run build` passed (TypeScript build plus Vite production bundle). Those were run after the recent Dashboard/Cases/Reports/notification frontend changes, before this documentation-only task. They were not rerun here.

**Backend runtime tests:** the latest focused pytest attempt against image ownership/content and analysis-run authorization stalled while executing the first selected test and was interrupted. It did not produce a pass/fail test result. A previous invocation initially used a wrong relative venv path and failed to start; a corrected invocation reached pytest but stalled. Backend pytest is therefore **unverified** for the latest changes. Backend source and existing tests contain owner-scoping checks, but source presence is not a live verification.

**Browser/database/model verification:** the user previously reported a successful live website analysis and a completed run with visualization outputs; a later message reported Grad-CAM available and rendered. Those are historical user reports, not rechecked in this documentation task. Current services, PostgreSQL migration head, model checkpoint loading, protected artifacts, frontend-to-backend behavior and current analysis run status are **not independently verified here**. No training or inference was run while preparing these documents.

## Current limitations and open verification

- Outputs are not clinically validated. Candidate regions are predictions, and the provisional stenosis threshold is configurable.
- The Attention U-Net mask is based on the dataset's syntax annotation union; code/docs do not establish that it traces lumen boundaries. Percentage narrowing is experimental predicted-mask width in pixels, not physical or validated lumen narrowing.
- Severity supports Normal/Mild/Moderate/Critical only; no Severe category is present. Thresholds are user-specified project rules.
- Inference is synchronous with a timeout. There is no background queue, automatic retry, or job progress stream.
- U-Net++ checkpoint and ML environment are outside normal source paths / separately configured; current external path existence and actual runtime package/checkpoint compatibility are unverified.
- Users and Settings pages remain mostly preview/disabled. Backend notification records are not integrated with the in-memory report-download notification bell.
- No real browser run, live database verification, or real-model inference was performed for this documentation task.

## Important files to inspect before implementation changes

Start with the narrow feature files and contracts before editing:

- `src/App.tsx`, `src/auth/AuthProvider.tsx`, `src/auth/api.ts`, `src/auth/ProtectedRoute.tsx`
- Relevant page under `src/pages/` plus matching `src/features/*` helper/hook and `src/styles.css`
- `backend/app/api/v1/endpoints/<feature>.py`, matching `backend/app/schemas/`, `models/`, `services/`, and `backend/tests/`
- `backend/app/core/config.py`, `backend/app/api/deps.py`, `backend/migrations/versions/` for environment/authorization/schema changes
- `ml/inference/pipeline.py`, both adapters, `ml/inference/worker.py`, `ml/inference/run_pipeline.py`, focused `ml/tests/`

