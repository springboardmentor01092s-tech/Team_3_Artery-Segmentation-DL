# Artery Analysis System — Updated Project Handover

**Repository:** `C:\Users\namde\artery-stenosis-project`  
**Purpose:** Current-state handover for a future developer or assistant. Read alongside [the updated codebase overview](CODEBASE_OVERVIEW_UPDATED.md).

## Evidence and safety

This handover reflects source inspection in the current repository. Code presence is not proof of a successful deployment or clinical performance. No credentials, patient records, image contents, model weights, training, inference, database changes, or application tests were accessed or run while preparing these documents. The existing `CODEBASE_OVERVIEW.md` and `PROJECT_HANDOVER.md` were left untouched.

## Project decisions and scope

- Preserve the React 19 + Vite + TypeScript frontend and FastAPI + SQLAlchemy + PostgreSQL backend.
- Authentication is administrator-provisioned; roles are admin and regular user. Protected data access must remain authenticated and owner-scoped, with admin access handled by existing authorization rules.
- Patient, case, image, preprocessing, and synchronous analysis workflows are represented in the current implementation. Uploaded image originals and generated artifacts are stored outside the database; database rows retain metadata and storage keys.
- The two model adapters process the original image independently: Attention U-Net for artery-mask prediction and U-Net++/ResNet34 for stenosis-mask probabilities. The U-Net++ threshold is provisional. Candidate regions are predictions, not confirmed stenoses.
- Percentage narrowing and severity are experimental derived values. They are not clinically calibrated or validated. Do not describe syntax-mask widths as lumen diameters.
- Grad-CAM is an optional model explanation. The UI applies a JET-colored blend to the original for display; it is not a stenosis boundary.
- Reports are generated in the frontend from selected persisted analysis data. User notes are not saved to the backend. Notifications currently are not persistent.
- Do not fabricate patient/case records, measurements, predictions, analysis results, or report artifacts. Show unavailable states when actual data is absent.

## Current implementation map

### Frontend

- Routing and protected shells: `src/App.tsx`, `src/auth/AuthProvider.tsx`, `src/auth/ProtectedRoute.tsx`.
- Authenticated API helpers: `src/auth/api.ts` (`apiRequest`, `apiRequestBlob`).
- Dashboard: `src/pages/DashboardPage.tsx`, `src/features/dashboard/dashboard-data.mjs`.
- Patients and cases: `src/pages/PatientsPage.tsx`, `src/pages/CasesPage.tsx`, `src/features/cases/case-preview.mjs`.
- Upload/preprocess/analysis launch: `src/pages/UploadAnalysisPage.tsx`.
- Run results and visualizations: `src/pages/ResultsPage.tsx` plus helpers under `src/features/analysis/`.
- Reports and exports: `src/pages/ReportsPage.tsx`, `src/features/reports/pdf-report.mjs`, `src/features/reports/report-data.mjs`, `src/features/reports/report-exports.mjs`.
- Account/admin-preview/settings: `src/pages/UsersPage.tsx`, `src/pages/SettingsPage.tsx`.
- Notifications/top navigation: `src/notifications/NotificationProvider.tsx`, `src/components/TopBar.tsx`.

### Backend and ML

- Application/config/API routing: `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/v1/router.py`.
- Auth and user provisioning: `backend/app/api/v1/endpoints/auth.py`, `backend/app/api/v1/endpoints/users.py`, `backend/app/core/security.py`, `backend/app/cli.py`.
- SQLAlchemy entities and schemas: `backend/app/models/`, `backend/app/schemas/`; migrations in `backend/migrations/versions/`.
- Patients/cases/images/preprocessing/analysis APIs: `backend/app/api/v1/endpoints/`.
- Storage, preprocessing, analysis orchestration and derived metrics: `backend/app/services/`.
- Model definitions/adapters/pipeline: `ml/models/`, `ml/inference/`; isolated inference dependencies are declared in `ml/requirements-inference.txt`.

## Workflow state

1. **Login:** frontend submits to `/api/v1/auth/login`, stores the access token in local storage, loads `/api/v1/auth/me`, and restores session on reload. Logout clears the session. Backend uses Argon2 password hashing and JWT validation. Account creation is admin/CLI provisioned, not public registration.
2. **Patient and case:** authenticated frontend CRUD calls use existing APIs. Cases require a patient association; backend applies owner/admin rules.
3. **Image upload:** upload is case-scoped and authenticated. PNG/JPG/JPEG are supported; server checks extension/content, dimensions/pixel bounds, file size, generates safe names, and stores the file locally. The image record is persisted in PostgreSQL.
4. **Preprocessing:** explicit action retrieves the saved original via established storage, creates a baseline representation, and persists status/metadata only. It does not perform segmentation and does not store transformed pixels in the database.
5. **AI analysis:** explicit synchronous request creates an analysis run. A private worker bridge invokes the isolated ML Python environment; both models receive the same original input independently. Runs and artifact metadata/status are persisted. There is no job queue or automatic retry implementation.
6. **Results:** the owner-scoped API returns saved run metadata; protected artifact requests use the shared bearer-token helper. Results UI can display returned masks, candidate overlay, combined visualization, Grad-CAM, and experimental derived metrics when present. Missing fields/artifacts must remain unavailable, not fabricated.
7. **Reports:** selected run data drives PDF, JSON, and CSV export. PDF includes run-specific visualizations where available. No backend report persistence or clinical sign-off is implemented.

## Known gaps and cautions

- User Management and Settings are frontend preview/placeholder experiences; do not assume they manage backend users or persist preferences.
- Notification panel behavior is in-memory and primarily tied to report download events. Backend currently exposes notification retrieval but not a full persisted create/read lifecycle.
- Reports do not have backend persistence. Notes remain temporary.
- Analysis is synchronous; the UI can show request-level waiting but cannot show truthful per-stage percentages. No queue, retries, or background progress events are present.
- Grad-CAM availability depends on the inference response/run artifacts; never promise it for every run.
- Severity thresholds are experimental project rules and do not include a Severe category in the currently inspected implementation. Unavailable/ambiguous narrowing should not be classified.
- The Attention U-Net syntax training target is not established as a lumen annotation. Do not interpret its boundary or pixel widths as calibrated lumen diameter.
- The external U-Net++ checkpoint and isolated ML environment are outside the normal source package. Their current path existence, compatibility, and runtime availability were not revalidated as part of this documentation task.
- The current configured live database migration state, service health, and browser end-to-end behavior were not checked for this handover.

## Verification record

- **Frontend:** the most recent recorded `npm test` result in this conversation was 43/43 passing; the corresponding `npm run build` completed successfully. These are previously recorded results, not rerun for this documentation task.
- **Backend:** the most recent attempted focused pytest command stalled while running a selected API test and was interrupted. Backend tests are therefore **unverified**, not passed.
- **Browser:** the user previously reported a successful live analysis and visible results/Grad-CAM. This is historical user-reported behavior, not independently rechecked here.
- **Clinical validation:** none established. No clinical accuracy or diagnostic claims are supported.

## Safe continuation checklist

1. Read `CODEBASE_OVERVIEW_UPDATED.md` and inspect the exact route, schema, service, and frontend consumer before changing an API contract.
2. Preserve auth dependencies and owner-scoped query filters. Test attempts to access another owner's IDs.
3. Keep original uploaded files immutable; store derived artifacts via private storage keys and serve them through authorized endpoints.
4. Preserve run-specific thresholds/model metadata. Never replace missing model output with a mock value.
5. Do not change checkpoints, thresholds, preprocessing, or model architecture without explicit task scope and focused tests.
6. For UI work, use current components and styles; add focused tests and run frontend test/build commands.
7. For backend work, use the existing backend environment and test conventions. Do not reset the database or remove volumes. Verify migrations without destructive operations.
8. Report separately what source implements, what automated checks actually ran, and what was manually observed in the browser.

## Milestone 4 — Task 7 security status (2026-11-25)

Focused security work added shared database-backed login throttling, email-change verification, private no-store headers for image/analysis artifacts, and safer analysis-worker diagnostics. See [SECURITY_TESTING_TASK_7.md](SECURITY_TESTING_TASK_7.md) for scope, exact paths, configuration and command output summaries.

- Automated focused SQLite API checks: 6 passed; analysis artifact/logging/worker checks: 3 passed; frontend email-verification contract checks: 2 passed.
- Dedicated PostgreSQL last-active-admin concurrency checks exist but were skipped: the dedicated database URL was unset, port 55433 was not listening, and Docker Desktop was inaccessible. PostgreSQL concurrency is not verified.
- Email verification code and mocked-send tests are present, but real SMTP delivery is unverified and unavailable until the operator configures the provider settings named in `backend/.env.example`.
- Migration `0006_security_controls` is required and has not been applied in this task. Apply it only through the approved deployment process after confirming the target database and backup.
- The API limiter uses atomic database upserts and fails closed until its migration is available. Behind a reverse proxy, configure a trusted proxy boundary; the app does not trust arbitrary forwarding headers.
- No full backend/frontend suite, browser test, migration, live database operation, SMTP delivery or security scanner was run for this task. `npm run build` completed successfully as a compile check.

No separate Master Progress Document was present among the repository's current Markdown documentation files; this status was added here to the existing updated project handover rather than creating or overwriting an unrelated master document.
