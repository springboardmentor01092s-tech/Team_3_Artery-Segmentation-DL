# Artery Analysis API

FastAPI/PostgreSQL backend for local development. The existing Vite frontend remains separate and is not yet wired to these APIs. Analysis uses a synchronous API request bridged to an isolated ML virtual environment; this is not a background queue and produces no clinically validated result.

## Local setup (PowerShell)

1. From the project root, prepare private app and database environment files and edit every placeholder. Use the same PostgreSQL database name, username, and password in both files:

   ```powershell
   Copy-Item backend/.env.example backend/.env
   Copy-Item backend/.postgres.env.example backend/.postgres.env
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Put the generated value in `SECRET_KEY`; set a new local-only `POSTGRES_PASSWORD` in both files. Keep both private files out of version control. Compose passes only the database credentials to the PostgreSQL container.

2. Start the PostgreSQL service from the project root (Docker Desktop required):

   ```powershell
   docker compose up -d db
   ```

3. Create a Python virtual environment and install backend dependencies:

   ```powershell
   cd backend
   py -3.10 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   alembic upgrade head
   python -m app.cli create-admin --email admin@example.local
   uvicorn app.main:app --reload
   ```

   The API is served at `http://127.0.0.1:8000`, Swagger docs at `/docs`, and the database-backed readiness check at `/api/v1/health`.

4. In a second terminal, start the unchanged frontend from the project root with `npm run dev`. CORS origins are configured using `CORS_ORIGINS` in `backend/.env`.

To use a locally installed PostgreSQL instead of Docker, set `DB_HOST`, `DB_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` to that local instance and skip the compose command.

## Initial API

All routes use the `/api/v1` prefix.

| Method | Route | Access | Behavior |
|---|---|---|---|
| GET | `/health` | Public | Checks API database connectivity; returns 503 if PostgreSQL is unavailable. |
| POST | `/auth/login` | Public | Accepts JSON email/password and returns a short-lived bearer token. |
| GET | `/auth/me` | Authenticated | Returns the caller's account and role. |
| GET, POST | `/users` | Admin | Lists accounts or creates an administrator-created account; no public registration. |
| GET, POST | `/patients` | Authenticated | Lists only the caller's patients; admins can list all. Create supports admin-assigned ownership. |
| GET, PATCH | `/patients/{patient_id}` | Authenticated | Reads or updates an owned patient; admins can access all. A non-owner receives 404. |
| GET, POST | `/cases` | Authenticated | Lists owned cases or creates a case under an accessible patient. |
| GET, PATCH | `/cases/{case_id}` | Authenticated | Reads or updates an owned case; admins can access all. A non-owner receives 404. |
| POST | `/cases/{case_id}/images` | Authenticated | Uploads validated PNG/JPG/JPEG bytes to local storage and records metadata in PostgreSQL. |
| GET | `/cases/{case_id}/images` | Authenticated | Lists images only when the caller can access the case. |
| GET | `/images/{image_id}/content` | Authenticated | Streams an image only to its owner or an admin. |
| POST | `/images/{image_id}/preprocess` | Authenticated | Validates and prepares the stored image in memory for a future ML consumer; returns metadata only and does not run a model or persist the transformed array. |
| GET | `/cases/{case_id}/preprocessing` | Authenticated | Lists preprocessing status and saved metadata for every image in an accessible case. |
| POST | `/cases/{case_id}/analysis-runs` | Authenticated | Accepts `{"image_id":"<UUID>"}` for an image in the accessible case, persists a run, and synchronously returns its `processing`, `completed`, or `failed` state. |
| GET | `/cases/{case_id}/analysis-runs` | Authenticated | Lists actual runs for an accessible case, newest first; a non-owner receives 404 and admins can access all cases. |
| GET | `/analysis-runs/{run_id}` | Authenticated | Returns owner/admin-scoped run status and persisted non-pixel metadata. |
| GET | `/analysis-runs/{run_id}/results` | Authenticated | Returns run status; on completion includes model metadata, candidate metadata, and protected artifact URLs. |
| GET | `/analysis-runs/{run_id}/artifacts/{artifact_name}` | Authenticated | Streams one allowlisted output artifact to its case owner or an admin. |
| GET | `/notifications` | Authenticated | Lists only notifications belonging to the caller. No notification producer is implemented yet. |

The first administrator is created locally with the CLI command above. Later user accounts are created through the administrator-only API. Patient, case, image, analysis-run and artifact ownership is checked server-side; record IDs do not grant access by themselves.

## Synchronous inference bridge

The API process does not import PyTorch or SMP. It starts `ml/.venv/Scripts/python.exe` lazily and privately, with a randomly generated per-process token, binding the isolated persistent model worker to `127.0.0.1`. Model weights are loaded once in that worker and inference requests are serialized to limit CPU memory use. A per-image invocation of `ml/inference/run_pipeline.py` communicates with the worker and writes the five outputs into a run-specific directory under `ANALYSIS_OUTPUT_DIRECTORY`, which is not mounted as static/public content. Backend validates array metadata, binary masks, finite probabilities, artifact names, file contents, and path containment before marking a run completed. PostgreSQL stores status, model/preprocessing/threshold metadata, timings, candidate metadata, and relative artifact keys only; pixel arrays are not persisted. The original source is reused from the protected image-content endpoint.

Configure `ML_PYTHON_EXECUTABLE` if the ML environment is not at the default path. Configure `ATTENTION_CHECKPOINT_PATH` and `UNETPP_CHECKPOINT_PATH` to private checkpoint locations when needed; never place real weights in frontend/public folders or commit them. The U-Net++ threshold defaults to provisional `0.20`; each run records it in model metadata. Candidate regions are labels from model output only. Grad-CAM is recorded as unavailable because its source method could not be recovered, and outputs are not clinically validated.

This initial integration is synchronous: the POST request remains open for CPU inference, bounded by `ANALYSIS_TIMEOUT_SECONDS`. There is no background job queue or automatic retry system. Apply the additive analysis metadata migration with `alembic upgrade head` before using the endpoints against PostgreSQL. The focused API tests use an injected fake inference bridge and do not load models; the isolated ML environment and real checkpoints are prerequisites for live inference.

Image size is capped by `MAX_UPLOAD_SIZE_BYTES` (10 MiB default, configurable up to 100 MiB) and decoded dimensions by `MAX_IMAGE_PIXELS` (40 million default). Content is decoded and verified with Pillow, and must match its `.png`, `.jpg`, or `.jpeg` extension. Files are stored under the ignored `UPLOAD_DIRECTORY` using random server-generated names; the original name is retained only as metadata.

## Initial preprocessing baseline

`POST /api/v1/images/{image_id}/preprocess` is authenticated and scopes image lookup to the owning case (admins may access any case). It resolves the existing server-generated storage key through the storage safety helper, applies the configured upload-byte and decoded-pixel limits, and revalidates the stored content and extension before processing. Missing or inaccessible image records return 404; invalid/corrupted content returns 415; size-limit violations return 413. PNG, JPG, and JPEG follow the upload validator.

The reusable service in `app/services/preprocessing.py` returns an in-memory NumPy array and metadata. The provisional default target is 256×256 because that is the only input shape shown in the current U-Net smoke test; no training dataset or verified preprocessing specification is present. The image is converted to one grayscale channel (Pillow luminance conversion for supported 8-bit RGB/palette/multichannel images; unsigned grayscale values are retained for supported 16-bit images), resized with Lanczos to fit while preserving aspect ratio, centered on zero padding, then mapped linearly from the full unsigned source range (0–255 or 0–65535) to float32 [0,1]. There is no per-image contrast stretching. The returned array is contiguous `float32`, shape `[1, height, width]` in CHW order; a batch can be added as `[1, 1, height, width]` for the current U-Net interface. The target can be changed by passing `PreprocessingConfig(target_size=(width, height))` to the service. On successful completion, a new additive migration stores only the status, attempt count, actor ID, and result metadata JSON per image; the transformed pixel array is discarded, and the original remains read-only. Failed attempts store a failure status/message and clear any previous result metadata so the page can offer a retry. `GET /cases/{case_id}/preprocessing` reports `not_started`, `completed`, or `failed` per saved image. Neither endpoint runs segmentation, produces measurements, or claims clinical analysis.

## Checks

Install the listed development test dependencies, then from `backend/` run `python -m compileall -q app migrations` and `pytest`. With PostgreSQL available and `.env` configured, run `alembic upgrade head`, then `alembic downgrade -1` and `alembic upgrade head` to verify migration/reversal. These commands are documented only; the current environment may not have dependencies or PostgreSQL installed.

## Milestone 4 Task 7 security controls

Login throttling uses atomic upserts in PostgreSQL (`login_rate_limit_buckets`), so limits are shared by API workers. The default is 10 attempts per 15 minutes for each HMAC-keyed client-IP and normalized-email bucket. Only keyed digests are persisted, not raw emails or addresses. The limiter fails closed with a generic 503 when its shared database operation is unavailable. Apply migration `0006_security_controls` with `alembic upgrade head` before deployment; until then, login is intentionally unavailable because the required limiter table is absent. The backend uses `request.client.host`; deployments behind a reverse proxy must configure a trusted proxy boundary so ASGI receives the intended client address. Do not trust arbitrary forwarded headers.

Email changes remain pending until confirmed through a random single-use link. Only a SHA-256 digest is stored; the default expiry is 30 minutes and resend requests are cooled down for 60 seconds. Confirmation changes the login email and increments the user's token version, invalidating existing sessions. To enable delivery, set these values in the ignored `backend/.env` (never commit it): `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, `SMTP_USE_SSL`, `SMTP_STARTTLS`, and optionally both `SMTP_USERNAME` and `SMTP_PASSWORD`; set `EMAIL_VERIFICATION_FRONTEND_URL` to the public frontend origin and `EMAIL_VERIFICATION_TTL_MINUTES` as required. For port 587 use STARTTLS (`SMTP_USE_SSL=false`, `SMTP_STARTTLS=true`); for implicit TLS use `SMTP_USE_SSL=true`, `SMTP_STARTTLS=false`. Configure valid provider credentials and sender authorization through the chosen mail provider; no SMTP account or credentials are included in this repository. Without complete SMTP settings the profile endpoint refuses email-change requests and leaves the existing login email unchanged.

The dedicated PostgreSQL concurrency tests are `tests/test_postgres_security_concurrency.py`. They require the separate `compose.security-test.yaml` service and `CORONAI_SECURITY_TEST_DATABASE_URL`, guarded to a loopback PostgreSQL database named `coronai_security_test` on port `55433`. The tests create and remove only a random schema inside that dedicated database; they reject other hosts, ports, names, users, or database drivers before connecting. Start only the test database service (not the application `db` service) using `docker compose -f compose.security-test.yaml --profile security-test up -d security-test-db`, after supplying a temporary test-only `CORONAI_SECURITY_TEST_POSTGRES_PASSWORD` via a local secret mechanism. Then set `CORONAI_SECURITY_TEST_DATABASE_URL` in the test process and run `python -m pytest -q tests/test_postgres_security_concurrency.py`. Never point it at the development database.

Downgrading migration `0006_security_controls` drops login-rate buckets and pending email-verification records. This resets active throttle windows and invalidates outstanding confirmation links; it does not alter user accounts or current emails. Coordinate any downgrade with the matching application rollback.

Private image and analysis artifact responses use `Cache-Control: private, no-store`. Analysis failures return a generic failure state and log only the run identifier and exception class; isolated worker stderr is suppressed, and the worker environment is allowlisted rather than inheriting application secrets. These controls have focused automated tests, but no live SMTP delivery or PostgreSQL concurrency run is represented by this source change.
