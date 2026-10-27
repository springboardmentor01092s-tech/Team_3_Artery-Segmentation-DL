# Artery Analysis API

FastAPI/PostgreSQL backend foundation for local development. The existing Vite frontend remains separate and is not yet wired to these APIs. No model inference, analysis worker, retry system, or clinical result generation is implemented.

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
| POST | `/cases/{case_id}/analysis-runs` | Authenticated | Returns 503 `analysis_unavailable`; creates no run and generates no results. |
| GET | `/analysis-runs/{run_id}` | Authenticated | Returns 404 because no runs are created; existing records are owner-scoped. |
| GET | `/analysis-runs/{run_id}/results` | Authenticated | Returns 503 `results_unavailable` for an accessible run; no findings or measurements are fabricated. |
| GET | `/notifications` | Authenticated | Lists only notifications belonging to the caller. No notification producer is implemented yet. |

The first administrator is created locally with the CLI command above. Later user accounts are created through the administrator-only API. Patient and case ownership is checked server-side; record IDs do not grant access by themselves.

Image size is capped by `MAX_UPLOAD_SIZE_BYTES` (10 MiB default, configurable up to 100 MiB) and decoded dimensions by `MAX_IMAGE_PIXELS` (40 million default). Content is decoded and verified with Pillow, and must match its `.png`, `.jpg`, or `.jpeg` extension. Files are stored under the ignored `UPLOAD_DIRECTORY` using random server-generated names; the original name is retained only as metadata.

## Initial preprocessing baseline

`POST /api/v1/images/{image_id}/preprocess` is authenticated and scopes image lookup to the owning case (admins may access any case). It resolves the existing server-generated storage key through the storage safety helper, applies the configured upload-byte and decoded-pixel limits, and revalidates the stored content and extension before processing. Missing or inaccessible image records return 404; invalid/corrupted content returns 415; size-limit violations return 413. PNG, JPG, and JPEG follow the upload validator.

The reusable service in `app/services/preprocessing.py` returns an in-memory NumPy array and metadata. The provisional default target is 256×256 because that is the only input shape shown in the current U-Net smoke test; no training dataset or verified preprocessing specification is present. The image is converted to one grayscale channel (Pillow luminance conversion for supported 8-bit RGB/palette/multichannel images; unsigned grayscale values are retained for supported 16-bit images), resized with Lanczos to fit while preserving aspect ratio, centered on zero padding, then mapped linearly from the full unsigned source range (0–255 or 0–65535) to float32 [0,1]. There is no per-image contrast stretching. The returned array is contiguous `float32`, shape `[1, height, width]` in CHW order; a batch can be added as `[1, 1, height, width]` for the current U-Net interface. The target can be changed by passing `PreprocessingConfig(target_size=(width, height))` to the service. On successful completion, a new additive migration stores only the status, attempt count, actor ID, and result metadata JSON per image; the transformed pixel array is discarded, and the original remains read-only. Failed attempts store a failure status/message and clear any previous result metadata so the page can offer a retry. `GET /cases/{case_id}/preprocessing` reports `not_started`, `completed`, or `failed` per saved image. Neither endpoint runs segmentation, produces measurements, or claims clinical analysis.

## Checks

Install the listed development test dependencies, then from `backend/` run `python -m compileall -q app migrations` and `pytest`. With PostgreSQL available and `.env` configured, run `alembic upgrade head`, then `alembic downgrade -1` and `alembic upgrade head` to verify migration/reversal. These commands are documented only; the current environment may not have dependencies or PostgreSQL installed.
