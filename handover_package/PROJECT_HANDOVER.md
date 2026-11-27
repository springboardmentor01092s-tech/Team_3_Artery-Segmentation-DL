# Project Handover

**Project:** Artery Segmentation and Stenosis Detection System  
**Prepared:** 2026-11-11 (Asia/Calcutta)  
**Source folder inspected:** `C:\Users\namde\artery-stenosis-project`

This handover combines the decisions and task history in the Codex conversation with a fresh inspection of the files. Use the current repository as the final authority. `CODEBASE_OVERVIEW.md` contains the detailed architecture, file map, endpoint inventory, schema, configuration, and execution notes.

## Requirements and decisions from the conversation

- Preserve the existing React/Vite/TypeScript frontend and its reference-matched design; do not rebuild or redesign unrelated pages.
- The selected reference screenshots are in `design-references/`; the eighth image is reference-only and must not become a Model Management page.
- Frontend stack is React 19 + Vite + TypeScript. Backend is FastAPI + SQLAlchemy 2 + Psycopg 3 + Alembic + Pydantic Settings. PostgreSQL is the intended local database. API prefix is `/api/v1`.
- Admin-created accounts only; roles are `admin` and `user`; no public registration. User data and image/case access must remain server-side owner-scoped. Never weaken authorization to satisfy UI/test needs.
- Do not fabricate patients, clinical measurements, predictions, findings, reports, or successful analysis states. Be explicit while a feature is unavailable.
- Uploaded medical images are sensitive. Keep actual credentials, patient data, uploaded image files, datasets, and checkpoints out of version control and handover archives.
- Work has been staged by milestone/task: authentication; case and patient management; image upload; preprocessing with persisted per-image state; baseline model training and CPU optimization; then investigation of a low smoke-run Dice. Do not silently expand a task into later features.
- Explicit prohibitions throughout: do not reset/delete DB data or migrations, never use `docker compose down -v`, do not create unnecessary virtual environments or reinstall dependencies, do not start duplicate servers on occupied ports, and do not expose secrets.

## Work recorded in the conversation

The project was first inspected before implementation. The frontend foundation and UI were built from the supplied screenshots, including Login and Dashboard. Later frontend work added Patient Management, Case Management, the unified Image Upload & Analysis route, Results, Reports, admin-preview User Management, and Settings layouts. The combined upload/analysis sidebar entry maps to `/upload`; `/analysis` redirects there. Model Management was intentionally not added.

Authentication was implemented and manually verified in the conversation. Later tasks connected patient and case CRUD to authenticated APIs, integrated image upload and protected image preview, persisted preprocessing status/results per image, restored selected case on refresh, and replaced the Cases image placeholder with real image counts. The user reported manually verifying patient/case persistence earlier. Those historical claims are not equivalent to a new live verification in this handover.

The backend foundation includes PostgreSQL config, auth and ownership checks, migrations, health endpoint, image storage, and preprocessing APIs. Analysis routes deliberately return unavailable responses. No model inference or fabricated clinical outputs are permitted.

The ML pipeline added an ARCADE syntax dataset reader and baseline training script using train/val splits, BCE-with-logits plus Dice, Adam, reproducible seeds, checkpoint/report output, CPU thread controls, configurable resolution and sample limits, and progress logging. A CPU smoke run used four training and two validation images for one epoch at 128×128. The user then requested investigation of validation Dice `0.0020`; prior inspection found the binary masks, image prep, threshold, and Dice implementation consistent, while the smoke model predicted nearly empty masks. The smoke checkpoint remains in the repository but is not a deployable model.

## Current repository status from direct inspection

### Connected application functions

- Login/current-user session, token persistence, protected routes and bearer-token API helper exist.
- Patient and case CRUD screens use the backend APIs; ownership checks are in backend dependencies/routes.
- Image upload/list/content previews use authenticated APIs and local backend storage.
- Explicit preprocessing uses the stored image, persists result metadata/status and supports retry after failure. The transformed pixel array is not persisted.
- Cases page obtains image counts from image list APIs.
- Local Attention U-Net weights and reports are present. The application backend does not load these weights, so end-user analysis remains unavailable.

### Important difference from earlier notes

The present tree now contains a 377 MB `ml/checkpoints/best_attention_unet.pt`, an Attention U-Net test report (300 images, Dice recorded as ~0.7597), a training report (best validation Dice ~0.8052), and a full baseline report. The baseline report refers to a Kaggle checkpoint path that is absent locally; the local baseline checkpoint is only the smoke run. These research artifacts indicate recorded model training/evaluation, but they do not mean model inference is connected, reproducibly verified now, or clinically validated. The handover archives intentionally omit all checkpoint weights and generated reports.

### Incomplete or placeholder areas

- Dashboard metrics/activity are static zero/empty preview data; only the case entry links navigate to Cases.
- Results has disabled selectors/tools and no real model results.
- Reports cannot select runs, generate/export reports, or save notes/section selection.
- Settings profile editing, preferences, notifications and recovery are not implemented.
- User Management UI remains placeholder despite admin-only backend `GET/POST /users` endpoints.
- Notifications are list-only; no event producer is present.
- No background analysis worker, job queue, automatic retry policy, or analysis status persistence is connected.
- Current preview notices and `backend/README.md` contain stale statements that conflict with connected patient/auth functionality.
- Training dataset is external and not packaged. ML dependencies are not separately declared/pinned.

## Historical versus fresh verification

The conversation records earlier passing frontend builds, backend tests, authentication manual checks, patient/case persistence checks, preprocessing persistence tests, and a baseline training smoke test. These are historical results, not rerun for this handover. A combined backend/ML pytest command was attempted while preparing the package, but no test summary was returned by the process session, so no current pass is claimed. Frontend build and live browser/database workflow were not rerun. PostgreSQL migration execution and real API startup were not checked for this handover. See the overview's verification section and rerun the checks before a code release.

## Pending work, in a safe order

1. Establish a fresh environment state: verify Docker/PostgreSQL, API health, migration head, frontend proxy, and current tests without starting duplicate services or altering persisted data.
2. Correct stale notices/docs and make the Dashboard's intended data-driven widgets explicit in scope before implementing them.
3. Implement actual admin user-management UI using existing APIs, with tests and server-side role enforcement preserved.
4. Design an explicit model-serving/inference integration task: decide model artifact lifecycle, preprocessing parity, run persistence, synchronous/background execution, failure/retry states, authorization, and auditability before connecting the Attention U-Net.
5. Only after real inference is safely integrated, implement result visualization and report generation from persisted model outputs. Never derive clinical claims from a training metric alone.
6. Add a separately pinned ML environment/manifest and document dataset provenance when training workflows are continued.

## Instructions to the next assistant

- Read `CODEBASE_OVERVIEW.md`, then inspect the named files in its “First files to inspect” section before editing.
- Do not recreate the app or assume the documentation in older README/notices is current.
- Confirm the user's scope for the specific task; implement only that milestone. Keep frontend/backend contracts aligned and add focused tests using existing conventions.
- Maintain user/case/image owner scoping, admin-only account administration, safe path resolution and upload content checks.
- Never expose `.env`, database credentials, signing secrets, access tokens, patient data, or image contents in logs or handover files.
- Do not put data or model checkpoints in source packages. Do not run destructive database/Compose operations.
- Treat all current model metrics as research/evaluation records, not clinical accuracy. Do not activate inference until a genuine model execution path and its input/output behavior are tested.
- Report what was actually run, what passed, and what remains unverified. Never infer an end-to-end success from source code or a build alone.

## Files delivered with this handover

- `CODEBASE_OVERVIEW.md`
- `PROJECT_HANDOVER.md`
- `artery-frontend-source.zip`
- `artery-backend-source.zip`

The archives are clean source snapshots; they deliberately do not contain runtime secrets, database contents, uploaded images, datasets, model checkpoints, or generated training reports.
