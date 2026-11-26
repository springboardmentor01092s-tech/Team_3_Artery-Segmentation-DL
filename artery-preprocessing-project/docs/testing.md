# Testing

## Backend

From `backend` with the virtual environment active:

```powershell
pytest -q
```

Coverage includes:

- Registration, login, invalid credentials
- Password hashing
- Expired and invalid JWTs
- Protected routes
- Role-based admin denial
- Ownership, shared access, revocation, and role-specific visibility
- Case create/retrieve/search/validation
- Unauthorized case access
- Valid upload, unsupported/corrupt/oversized rejection
- Preprocessing success, invalid parameters, original-image preservation, history persistence
- Analysis history, protected artifacts, validation comparison image access, exact ARCADE image/COCO matching, category/dimension guards, lesion-mask Dice/IoU/precision/recall/TP/FP/FN, candidate overlap, persisted comparison artifact, authorization, and JSON/CSV/PDF exports
- COCO category/mask behavior, metrics, normalization, focal losses, and train/validation-only routine audit
- Production secret and CORS configuration checks
- Configurable application file logging, rotation bounds, and repeat-configuration behavior (temporary log directories)
- Guarded diameter formula examples and rejection of missing calibration, invalid lumen/reference evidence, invalid diameters, and out-of-image locations
- Dashboard totals scoped to visible cases and administrator-only user totals
- Admin user listing, role and activation changes, self-deactivation rejection, audit access, and invalid input bounds

Tests use an in-memory SQLite database and temporary storage directories.

## Development continuation verification (2026-11-25)

After adding optional Integrated Gradients attribution and ARCADE ground-truth comparison, the full backend suite completed with **109 passed**, Python compilation (`python -m compileall -q app tests alembic`) passed, and the frontend suite completed with **37 passed across 12 files**. The Vite production build passed (1,685 modules). The focused ARCADE comparison/API/export tests completed with **13 passed**; Integrated Gradients/API/export tests completed with **9 passed**. These are automated regression checks; they do not count as manual browser, security, performance, medical-validation, or deployment completion. See [final completion audit](final_completion_audit.md) and the master [project checklist](project_requirement_checklist.md).

## Frontend

```powershell
cd frontend
npm test
```

Frontend tests cover login success/error, case-list empty/authorized/error states, case creation, preprocessing loading/success/error, image upload, segmentation feedback, candidate/visualization rendering, unavailable diameter-measurement display, report-download requests, API token/error handling, dashboard role statistics and errors, admin user/audit states, nested application routes, role restrictions, navigation visibility, and redirects. Full browser-based workflows still need manual verification.

## Lumen geometry continuation verification (2026-11-25)

The geometry-only helper has synthetic-mask tests for known pixel widths, guarded calibrated synthetic calculation, anisotropic spacing orientation, absent/unverified calibration, required expert-validation gates, empty/misaligned masks, disconnected lumen components, and overlay drawing. These tests do not validate a real angiogram or clinical measurement. API tests assert normal lesion analysis keeps pixel/mm diameters unavailable and never treats a candidate box as lumen width; frontend tests assert pixel/mm fields remain unavailable and calibration/transform verification are false. The full backend suite passed with **120 passed**; Python compilation passed; frontend passed **37 tests across 12 files**; Vite production build passed (1,685 modules). No manual browser, clinical, security, performance, or deployment testing was performed.

## Analysis history, CSV export, and segmentation workflow fix (2026-11-25)

The history endpoint had been evaluating a SQLAlchemy `Select` object as a boolean, which raises `TypeError` instead of returning records. The check was removed; history now queries the user's visible case IDs directly and supports server-side search, mode filtering, and pagination. CSV exports now include saved case/image/preprocessing and analysis fields, preserve nested metadata as JSON cells, and distinguish missing source values from numeric zero. The history page uses these server-side filters and provides direct links to its case analysis.

- Backend: **127 passed** (`.venv\\Scripts\\python.exe -m pytest -q`). The new isolated integration test uploaded the existing 512x512 ARCADE validation sample to temporary test storage, ran the existing `best_stenosis_unet_optimized.pth` through the lesion analysis endpoint, verified the stored binary mask and overlay dimensions, retrieved that same analysis through history, and verified that the checkpoint SHA-256 did not change. It does not validate clinical performance.
- Frontend: **53 passed across 17 files** (`npm.cmd test -- --run`).
- Python compilation: passed (`.venv\\Scripts\\python.exe -m compileall -q app tests alembic`).
- Vite production build: passed, **1,689 modules** (`npm.cmd run build`).

The CSV/history tests use isolated database fixtures; the real-image smoke test stores artifacts in a temporary directory. They do not perform manual browser testing, deployment, clinical validation, or a full user session against the persistent database.

## Latest automated run

On 2026-11-25, after DICOM provenance, ARCADE split inventory, migration and local logging changes, the full backend suite completed with **99 passed**, Python compilation (`python -m compileall -q app tests alembic`) passed, and the frontend suite completed with **35 passed across 12 files** (`npm.cmd test -- --run`). The Vite production build passed (`npm.cmd run build`, 1,685 modules). Focused backend tests passed: **12** for preprocessing/analysis, **8** for dataset summary, **2** for migrations, and **12** for logging/configuration; focused frontend tests passed: **3** for CaseDetailPage and **2** for DatasetPage. CPU inference on a 512×512 validation sample produced a mask, candidates, overlay, boxes visualization, and probability heatmap; narrowing/severity remained unset. No manual browser, security, performance test, or deployment was performed. These automated checks do not certify a browser session, deployment, lumen measurements, or clinical validity.

## Manual API tests

1. Start the backend.
2. Open `/docs`.
3. Register, login, copy `access_token`.
4. Click Authorize and paste the token.
5. Create a case, upload a PNG, run preprocess, fetch history.

## UI workflow continuation verification (2026-11-25)

After adding routed upload, analysis history, report export and model comparison pages, dashboard recent cases/activity, and the responsive shared shell, the complete frontend suite passed: **50 tests across 17 files**. The Vite production build passed with **1,689 modules**. The backend suite passed with **120 tests**, and Python compilation passed using `python -m compileall -q app tests alembic`.

New component coverage includes upload selection/permission/error/success path; history loaded, search/filter states; JSON/CSV/PDF report requests; checkpoint metadata and saved validation scores; route reachability/navigation; dashboard recent-case rendering; profile update/error and password clearing; and preprocessing permission/busy states. The checks used mocked APIs for React components and the backend's existing isolated test configuration. They do not certify a browser session or live API workflow. No manual browser, dedicated security, performance, clinical, or deployment testing was performed.

The first complete frontend run found two stale dashboard test-fixture assumptions after the page began loading recent cases and the shared shell owned the page title. The fixture/assertion was corrected; the final full frontend run passed.


## Remaining-requirements continuation verification (2026-11-25)

After the readiness probe, request telemetry, final-active-administrator guard, audit-log refresh, and report Blob URL lifetime changes:

- Backend: **123 passed** (`.venv\\Scripts\\python.exe -m pytest -q`).
- Frontend: **51 passed across 17 files** (`npm.cmd test -- --run`).
- Python compile: passed (`.venv\\Scripts\\python.exe -m compileall -q app tests alembic`).
- Vite production build: passed, **1,689 modules** (`npm.cmd run build`).

Health tests cover successful and unavailable database probes. Telemetry tests ensure a query-string token is not included in logged fields. Admin API tests verify the sole active administrator cannot be demoted. UI tests verify audit refresh and that export Blob cleanup is deferred. These automated checks are not manual browser, security, performance, or deployment validation. The model registry, external log collector, and alerting service are not present/configured.
