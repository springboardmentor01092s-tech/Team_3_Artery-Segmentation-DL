# Project-wide requirement checklist

Audit date: 2026-11-25. This is an implementation audit, not a manual browser or deployment sign-off.

## Source-of-truth scope

The original project-requirements source supplied for this audit is `C:\Users\aksha\Downloads\Artery_Segmentation_and_Stenosis_Detection_Using_Advanced_DL_Techniques (1).pdf`. The current user-pasted continuation prompt is the execution instruction; the PDF is the requirements source. Where the prompt explicitly excludes work (in particular lumen/diameter measurement, retraining/checkpoint changes, and manual, security, performance, or deployment testing), those exclusions govern this continuation even though the PDF describes broader project goals. The PDF's four-milestone requirements are cross-referenced below with the existing 40-item audit matrix and code evidence. The project has no Git metadata, so preservation was checked using hashes and inventories.

Status meanings: **Verified** means an automated test or recorded execution supports the task; **Implemented / manual verification pending** means code and automated coverage exist but the user reserved browser/deployment checks; **Partial** means material capability is missing; **Blocked** means required external data/service/environment is unavailable; **Not promoted** means an experiment was deliberately retained separately.

## Milestone 1 — dataset, preprocessing, storage and application foundation

| ID | Required task and implementation path | Status and evidence |
|---|---|---|
| M1.1 | Windows-safe settings/environment/storage — `backend/app/core/config.py`, `backend/app/arcade_ml/paths.py`, `.env.example` | **Verified** by config tests; no user-specific project path is required. |
| M1.2 | ARCADE split/path discovery and dataset summary — `backend/app/arcade_ml/paths.py`, `backend/app/services/dataset_service.py`, `backend/app/api/dataset.py`, `frontend/src/pages/DatasetPage.jsx` | **Implemented and automated-verified locally**: reports stenosis/SYNTAX train and validation images/COCO counts; test images are identified as holdout, while test annotations are never opened. |
| M1.3 | COCO parsing, category filtering, polygon masks — `backend/app/arcade_ml/coco.py`, `dataset.py`, `backend/tests/test_dataset.py` | **Verified** for lesion and SYNTAX task semantics. Lesion polygons are not lumen labels. |
| M1.4 | Train/validation integrity, duplicate handling, test holdout — `backend/app/arcade_ml/audit_validation.py`, `backend/tests/test_ml_validation.py` | **Partial**: routine training/model selection is train/validation-only; a historical full integrity audit inspected test files. |
| M1.5 | Image read, PNG/JPEG/DICOM conversion, preprocessing history — `backend/app/preprocessing/pipeline.py`, `backend/app/api/cases.py`, `backend/app/models/preprocessing.py` | **Verified** by preprocessing, invalid-input, history and original-preservation tests. Multi-frame DICOM is unsupported. |
| M1.6 | DICOM metadata capture incl. PixelSpacing — `pipeline.py`, `backend/app/services/image_service.py`, `backend/app/models/image.py`, analysis API and case detail | **Implemented and automated-verified for metadata provenance**: finite positive row/column values are retained; malformed/missing values are labeled; analysis history, UI and exports expose them with `used_for_measurement: false`. No real DICOM case was available. This does not establish physical calibration suitability; that remains blocked under M3.5. |
| M1.7 | Database models and additive initialization/migration — `backend/app/models/`, `backend/app/database/`, `backend/alembic/` | **Implemented and temporary-database verified** for fresh and legacy partial schemas; existing row preservation is tested. Target production migration remains unrun. Migration creates missing tables but does not alter columns in tables that already exist. |
| M1.8 | Registration, password hashing, login, JWT, profile — `backend/app/api/auth.py`, `backend/app/security/`, `frontend/src/pages/{Login,Register,Profile}Page.jsx` | **Verified** by backend and frontend tests. |
| M1.9 | Roles, protected routes, ownership/sharing/assignment — `backend/app/core/permissions.py`, `backend/app/api/cases.py`, `backend/app/services/case_service.py`, `frontend/src/routes/ProtectedRoute.jsx`, `frontend/src/App.jsx` | **Verified** by authorization and role tests. |
| M1.10 | Case CRUD, upload/source-image access — `backend/app/api/cases.py`, `backend/app/services/image_service.py`, `frontend/src/pages/{Cases,CaseDetail}Page.jsx` | **Verified** by API/component tests; browser flow remains manual. |

## Milestone 2 — segmentation, training, evaluation and inference

| ID | Required task and implementation path | Status and evidence |
|---|---|---|
| M2.1 | Lesion and experimental model architectures — `backend/app/arcade_ml/{models,inference}.py` | **Verified** for active lesion U-Net inference and separate research architectures. Targets have different semantics. |
| M2.2 | Dataset loader and augmentation — `backend/app/arcade_ml/{dataset,train_experiment}.py` | **Verified** by loader/training utility tests; experiments use train/validation. |
| M2.3 | Losses, metrics, training loop — `backend/app/arcade_ml/{losses,engine,metrics,train_experiment}.py` | **Verified** by tests and saved experiment reports. |
| M2.4 | Validation threshold selection/full evaluation — `backend/app/arcade_ml/{audit_validation,evaluate_syntax_vessels}.py` | **Verified** against validation labels. Same-validation threshold selection/scoring is exploratory, not independent clinical validation. |
| M2.5 | Checkpoint metadata/loading/compatibility — `backend/app/arcade_ml/inference.py`, `backend/app/core/config.py` | **Verified** by tests. Active checkpoint retained; experimental candidates not promoted. |
| M2.6 | Kaggle private bundle/notebook GPU workflow — `notebooks/arcade_gpu_model_sweep.ipynb`, `build_kaggle_bundle.py`, `collect_kaggle_results.py`, `kaggle_upload/` | **Blocked / live status unverified**: persisted handoff says Version 2 was QUEUED with GPU and inputs attached; fresh `kaggle.exe kernels status` failed with Windows network access denied. No current GPU execution is asserted and the kernel was not changed. |
| M2.7 | Kaggle results collection/baseline comparison — `notebooks/collect_kaggle_results.py`, `reports/kaggle_gpu_run/` | **Implemented, execution/output verification blocked**: no verified COMPLETE status or result bundle; collector was not run. |
| M2.8 | Local model comparisons and non-promotion of weaker candidates — `reports/model_validation/`, `reports/vessel_segmentation/`, `docs/model_validation_report.md`, `docs/vessel_segmentation_experiment.md` | **Verified** for recorded runs. SYNTAX models predict region labels, not lumen. |
| M2.9 | Integrated analysis inference on real validation sample — `backend/app/api/analysis.py`, `backend/app/arcade_ml/inference.py` | **Verified** by recorded 512×512 inference smoke run and automated API tests; not a browser test. |

## Milestone 3 — localization, visualization and measurements

| ID | Required task and implementation path | Status and evidence |
|---|---|---|
| M3.1 | Connected-component lesion candidates/localization — `backend/app/arcade_ml/{localize,postprocess,inference}.py` | **Verified**, with weak candidate precision documented in validation report. |
| M3.2 | Mask, overlay, boxes, probability map and explainability ? `inference.py`, `explain.py`, analysis API and case detail | **Implemented**: existing output visualizations remain; optional on-demand Integrated Gradients is tied to the analysis checkpoint SHA-256 and saved as a protected artifact. It is model sensitivity only, not clinical confidence or validated explanation. Automated checks are recorded below; browser/manual verification remains separate. |
| M3.8 | Exact ARCADE ground-truth comparison for a persisted analysis ? `backend/app/arcade_ml/ground_truth_comparison.py`, `/api/analyses/{id}/ground-truth`, `CaseDetailPage.jsx` | **Implemented and exercised on uploaded `case_008`**: exact filename/content hash, COCO ID/category/dimensions and stored-mask alignment verified; overlap metrics, per-candidate overlap, protected 4-panel visualization, JSON/CSV/PDF persistence. Single train image only; not independent/clinical validation. See [case report](ground_truth_comparison.md). |
| M3.3 | Experimental SYNTAX centerline/perpendicular pixel widths — `backend/app/arcade_ml/vessel_width.py`, analysis API, case page | **Implemented and automated-verified** as widths of predicted vessel regions only; not lumen diameter. Real-image smoke run is not accuracy validation. |
| M3.4 | Actual lumen boundaries at lesion and healthy reference — no validated lumen model/labels in this project | **Blocked**: ARCADE stenosis annotations are lesions and SYNTAX masks are vessel-region labels. Neither is lumen-wall ground truth. |
| M3.5 | Physical lumen diameter (mm) — `backend/app/arcade_ml/diameter_measurement.py`; DICOM spacing provenance in preprocessing/analysis | **Blocked**: spacing metadata is now validated syntactically and displayed when reported, but there is no validated lumen contour/reference pair or verified angiographic calibration/transform provenance. Audited uploads are PNG. No pixel-to-mm conversion is made. |
| M3.6 | Automatic image-based stenosis percentage — guarded helper, analysis API/UI | **Blocked**: API correctly reports “Unable to calculate”; only synthetic arithmetic examples test the formula. |
| M3.7 | Clinical severity category | **Blocked**: no validated diameters, approved reference method, or clinical validation; severity remains null. |

## Milestone 4 — dashboard, reports, security, operations and handoff

| ID | Required task and implementation path | Status and evidence |
|---|---|---|
| M4.1 | Dashboard statistics scoped to visible cases — `backend/app/api/dashboard.py`, `frontend/src/pages/DashboardPage.jsx` | **Verified** by API and component tests. |
| M4.2 | Admin users and audit log - `backend/app/api/admin.py`, `frontend/src/pages/{AdminUsers,AdminAudit}Page.jsx` | **Verified** by auth/input/audit/UI tests; server prevents deactivating or demoting the last active administrator, and audit records can be refreshed in the UI. |
| M4.3 | Recent/case analysis history and protected artifacts — `backend/app/api/analysis.py`, `backend/app/models/analysis.py` | **Verified** by scope and artifact authorization tests. |
| M4.4 | JSON/CSV/PDF reports — analysis API, `CaseDetailPage.jsx` | **Verified** by export tests, including unavailable diameter fields; browser download remains manual. |
| M4.5 | Model metadata/validation comparison dashboard — analysis API, `DashboardPage.jsx` | **Implemented / browser verification pending**; stored metrics do not imply a new run. |
| M4.6 | API configuration, loading/empty/error/unauthorized UI — `frontend/src/api/client.js`, `utils/errors.js`, pages/routes | **Automated-verified** for tested views; full browser/network interactions remain pending. |
| M4.7 | Password/JWT config, permissions, input constraints, protected files, CORS — backend security/core/utils/API routers | **Automated-verified** for covered cases; manual/production security testing remains pending and was not performed. |
| M4.8 | Logging, audit events, error handling - `backend/app/utils/audit.py`, API routers, `backend/app/core/logging_config.py`, `backend/app/main.py` | **Implemented locally and automated-verified**: configurable rotating file logs; request method/route-template/status/latency telemetry without bodies/query values; `/api/health` performs a database readiness query and returns 503 when unavailable. Centralized production shipping/retention and production security review remain unconfigured. |
| M4.9 | Windows setup, API, model/data limitation docs — README and `docs/` | **Implemented**; the supplied original PDF and current continuation scope are now explicitly cross-referenced in this checklist. |
| M4.10 | Deployment readiness: HTTPS/secrets/storage/backups/target runtime | **Blocked pending target environment and user deployment**. Configuration guards are tested; no deployment performed. |
| M4.11 | Browser/manual end-to-end workflows | **Pending by user instruction**; automated API/component checks do not certify browser use. |
| M4.12 | Manual security and performance verification | **Pending**: no penetration/security review, load test, or target-environment performance test was performed. |

## Workflow integration evidence

| Workflow | Code path | Status |
|---|---|---|
| Login/profile | `/api/auth/*`; login/profile pages | Automated auth/API and login tests pass. |
| Dashboard | `/api/dashboard/stats`; `DashboardPage.jsx` | Role-scoped API/UI tests pass. |
| Case create/list/detail/access | `/api/cases`; `cases.py`, case pages | CRUD, access and UI tests pass. |
| Upload/image retrieval | `/api/cases/{id}/upload|image`; `image_service.py` | Validation and authorization tests pass. |
| Preprocess/history | `/api/cases/{id}/preprocess|preprocessing-history`; pipeline/page | Success/error/history tests pass. |
| Segmentation/candidates | `/api/cases/{id}/analyze`; inference/localization/page | API, artifact and component tests pass. |
| Candidate visualizations | `/api/analyses/{id}/artifacts/{name}` | Protected artifact and component tests pass. |
| Analysis history | `/api/analyses`, `/api/cases/{id}/analyses` | Scope/history tests pass. |
| Exports | `/api/cases/{id}/reports/{format}` | JSON/CSV/PDF tests pass; actual browser download is manual. |
| Admin users/audit | `/api/admin/*`; admin pages | Role/input/audit/UI-state tests pass. |
| Lumen/stenosis | guarded helper and unavailable API/UI payload | Correctly unavailable; image measurement remains blocked. |

## Verification and preservation

Latest automated results are in [testing.md](testing.md). No browser test, deployment, Kaggle modification, upload/dataset mutation, or checkpoint promotion was performed during the baseline audit. The later documented case comparison made one additive analysis-payload/artifact update and an audit row; no previous analysis fields were replaced. Baseline database SHA-256 before that requested update: `90b6cdb4b78d58105b3615e470ead0d388e1c462ee06d7f8a749f5362c0b8d2e`. Active checkpoint SHA-256: `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`. Protected storage and source/bundle counts and byte totals remain unchanged from the inventories in [final_completion_audit.md](final_completion_audit.md).

## Exact blockers

To unblock supportable lumen diameter and stenosis estimates, provide authorized access to invasive angiography in original or equivalently calibrated image form; valid pixel calibration plus transform provenance; expert-adjudicated inner-lumen contours at lesion and reference cross-sections or QCA MLD/reference values and coordinates; a defined reference-segment protocol; and patient-level splits with independent held-out evaluation. ARCADE lesion polygons and SYNTAX artery-region masks do not satisfy these requirements. Verify rights and annotation semantics before bringing in any external data. CT angiography labels alone do not validate measurement on invasive 2D angiograms.

Kaggle execution must finish before its outputs can be evaluated. Deployment needs a target and production configuration. Browser workflow testing remains assigned to the user.

## Supplied Infosys brief crosswalk and current UI continuation (2026-11-25)

This crosswalk records the original PDF requirements separately from the current implementation directives. “Partial/blocked” is not promoted to complete based on a UI route or placeholder; the detailed evidence remains in the milestone rows above and [final completion audit](final_completion_audit.md).

| PDF requirement group | Existing implementation / evidence | Current status |
|---|---|---|
| Authentication, role access, cases, upload and preprocessing | FastAPI auth/case/image APIs, React protected routes and workflow pages; backend and component tests | Implemented; automated checks pass; manual browser workflow remains pending. |
| Segmentation, localization, post-processing, training and evaluation | Active lesion U-Net, train/validation pipeline, saved model comparisons, candidates and visualizations | Implemented for research lesion-region prediction. Does not establish full-vessel or lumen segmentation; active weights were not changed in this continuation. |
| Quantitative narrowing, clinical severity and physical measurements | Guarded helper and unavailable-result response | Blocked: no validated lumen contours/reference measurements/calibration; this continuation expressly excludes implementing this area. |
| Explainable AI | Optional checkpoint-bound Integrated Gradients artifact and analysis UI | Implemented as input sensitivity only; not a validated clinical explanation or Grad-CAM. |
| Dashboard and case/analysis workflow | Scoped statistics, recent cases/activity links, cases/create/detail pages, upload, preprocessing, case analysis | Implemented and covered by automated component/API tests; live browser flow remains manual. |
| Reporting and exports | Case-scoped PDF/CSV/JSON API plus new Reports page; history supports search and mode filter | Implemented; format requests and related backend exports are automated-tested; actual browser download remains manual. |
| Model registry/comparison and operational monitoring | Checkpoint metadata/validation comparison UI, configured active checkpoint path, local rotating logs, route telemetry and database readiness probe | Partial: comparison is read-only metadata and saved evaluations; no registry/promotion/rollback API. No candidate has a verified improvement that could safely be promoted; active weights remain protected. Central monitoring backend is not configured. |
| Notifications/alerts, advanced analytics and project presentation/demo materials | Dashboard statistics/model comparisons/reports exist; no notification service or validated clinical alert policy | Partial/missing. Clinical stenosis alerts remain unsupported without validated severity measurements. No unsupported alert or diagnostic claim was invented. |
| Containerization/cloud deployment and production operations | Production configuration guards and setup documentation | Not completed: no target deployment, container runtime, cloud infrastructure, security review, or performance exercise in this continuation. |

The professional interface continuation added a consistent responsive application shell and routed pages for image upload, analysis history, report export, and read-only model comparison. Dashboard shortcuts and recent cases/activity were integrated; preprocessing and profile forms expose permission/busy/validation states. Follow-up work added a refresh action for audit logs, delayed report Blob URL cleanup until the browser can start the download, database readiness and privacy-minimal request telemetry, and protection against removing/demoting the final active administrator. No auth page or case analysis pipeline was recreated.

### Continuation verification

On 2026-11-25, after the continuation fixes, frontend Vitest completed with **51 passed across 17 files**; production Vite build completed successfully (1,689 modules). Backend pytest completed with **123 passed**; Python `compileall` passed. These verify automated tests/build only. No manual browser, deployment, dedicated security, performance, or clinical validation was done. Backend tests cover health, safe request telemetry, and final-admin protection; frontend tests cover audit refresh and report download URL lifetime.

Changed implementation files: `backend/app/main.py`, `backend/app/api/admin.py`, `backend/tests/test_health.py`, `backend/tests/test_cases.py`; frontend `App.jsx`/`App.test.jsx`, `layouts/AppLayout.jsx`, `index.css`, `DashboardPage.jsx`/test, `PreprocessPage.jsx`/test, `CreateCasePage.jsx`, `ProfilePage.jsx`/test, `AnalysisHistoryPage.jsx`/test, `ImageUploadPage.jsx`/test, `ReportsPage.jsx`/test, `ModelComparisonPage.jsx`/test, and `AdminAuditPage.jsx`/test. Documentation is recorded in README and `docs/{project_requirement_checklist,final_completion_audit,api_documentation,user_guide,testing}.md`. No database migration, checkpoint operation, dataset write, upload write, or artifact write was performed.

### Lumen geometry implementation update (2026-11-25)

`backend/app/arcade_ml/lumen_measurement.py` now provides an isolated geometry-only consumer for externally supplied expert-validated lumen masks and lesion/reference ROIs. It extracts a morphological centerline, estimates local axes, samples perpendicular boundary crossings, reports minimum/reference pixel diameters and locations, and renders contour/caliper overlays. Millimetre conversion requires valid DICOM row/column spacing plus explicit image calibration and transform verification. The helper delegates stenosis arithmetic to the existing guarded formula. It is not connected to ordinary analysis because the project has no suitable lumen annotations; normal API/UI results remain unavailable. Synthetic tests are implementation checks only, not real-image validation. M3.4–M3.6 therefore remain blocked for actual angiograms. Required data: expert-adjudicated invasive-X-ray inner-lumen contours and lesion/reference coordinates, calibrated original images with transform provenance, a QCA reference protocol, and independent patient-level validation. See [lumen measurement audit](lumen_measurement_completion_audit.md).

## Development continuation — ARCADE split inventory (2026-11-25)

Completed M1.2's missing application integration:

- `backend/app/services/dataset_service.py`: adds task/split inventory from configured `ARCADE_ROOT`; counts supported image filenames and parses only train/validation COCO annotations, filtering stenosis category 26 and SYNTAX categories 1–25. Test image counts are shown as holdout, but no test annotation path is opened or parsed.
- `backend/app/schemas/preprocessing.py`: defines typed nested split summary output.
- `frontend/src/pages/DatasetPage.jsx`: adds ARCADE task/split cards and explicit test holdout messaging while retaining sample and accessible-upload summaries.
- `backend/tests/conftest.py`, `backend/tests/test_dataset.py`: isolate ARCADE fixture data under temporary directories and assert COCO counts/category filtering and malformed test-annotation non-access.
- `frontend/src/pages/DatasetPage.test.jsx`: covers train/validation/test presentation and API error handling.

Read-only summary against the configured local ARCADE root reported: stenosis train 1,000 images/1,625 category-26 annotations; validation 200/406; test 300 images with annotations not inspected. SYNTAX train 1,000 images/4,976 category-1–25 annotations; validation 200/1,168; test 300 images with annotations not inspected. These are dataset inventory counts, not model results. Automated evidence: backend **94 passed**, frontend **35 passed in 12 files**, Python compileall passed, Vite production build passed (1,685 modules). The configured source dataset was read-only; the tests use temporary fixtures.

## Development continuation — additive Alembic upgrade path (2026-11-25)

Completed the feasible migration code/tests for M1.7:

- `backend/alembic/versions/0001_initial.py`: skips user-table creation if an existing unstamped database already has `users`.
- New `backend/alembic/versions/0004_complete_missing_tables.py`: additively creates any missing model tables and intentionally does not drop tables on downgrade.
- New `backend/tests/test_database_migrations.py`: runs `alembic upgrade head` against a fresh temporary SQLite database and a temporary legacy database containing an existing user row; verifies all tables and that row survive.
- `README.md`: documents backup, fresh/legacy behavior and the column-alteration limitation.

Focused migration tests: **2 passed**. They do not touch the application's SQLite database. Latest complete verification after all three continuations: backend **96 passed**, frontend **35 passed in 12 files**, Python compilation passed, and production build passed (1,685 modules). M1.7 remains target-environment pending: the current database was deliberately not migrated, and revision 0004 does not add columns to existing tables. A production schema with customized or older columns needs a reviewed explicit migration.

## Development continuation — DICOM spacing provenance (2026-11-25)

Completed M1.6's feasible metadata path without asserting measured lumen geometry:

- `backend/app/preprocessing/pipeline.py`: validates DICOM PixelSpacing as a finite, positive two-value row/column pair; records the DICOM calibration-type tag when supplied; marks absent and invalid spacing distinctly.
- `backend/app/api/analysis.py`: carries reported spacing into saved analysis/history and JSON/CSV/PDF exports. It labels the values as reported metadata and always sets `used_for_measurement` to false.
- `frontend/src/pages/CaseDetailPage.jsx`: displays reported spacing and its provenance/limitation beside the measurement panel.
- `backend/tests/test_pipeline.py`: tests valid, missing, malformed, zero, NaN and infinite spacing plus loading a generated DICOM object through the real parser.
- `backend/tests/test_analysis.py` and `frontend/src/pages/CaseDetailPage.test.jsx`: test API persistence/export semantics and UI rendering, including that stenosis remains unavailable.

Verification after this change: backend **93 passed**; frontend **33 passed in 11 files**; Python compileall passed; Vite production build passed (1,685 modules). Focused tests were `12 passed` for `test_pipeline.py` and `test_analysis.py`; focused case-detail tests were `3 passed`. The test DICOM is generated in a temporary test directory; no clinical image or project storage is changed. M1.6 is complete as reported-metadata acquisition and traceability, not as verified physical calibration or mm diameter calculation. M3.4–M3.6 remain blocked for the evidence gaps listed above.

## Development continuation — configurable local logging (2026-11-25)

Completed the locally implementable portion of M4.8:

- New `backend/app/core/logging_config.py` installs an idempotent UTF-8 `RotatingFileHandler` for application loggers.
- `backend/app/core/config.py` supports `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT`; paths resolve relative to the backend unless absolute.
- `backend/app/main.py` configures the sink before database initialization and logs startup completion.
- `backend/.env.example` and `README.md` document the local default, rotation bounds and sensitive-data guidance.
- New `backend/tests/test_logging_config.py` verifies writing, bounded rotation, handler replacement and startup ordering using temporary directories.
- `backend/tests/conftest.py` disables file logging for API tests so test startup cannot write to the configured developer log path.
- `backend/app/api/analysis.py` no longer includes the case identifier in inference-failure log messages.

Focused logging/config tests: **12 passed**. Local file logging is implemented; centralized production log shipping/retention and manual security review remain unconfigured/not performed.

Kaggle was checked without changing it: `.venv\\Scripts\\kaggle.exe kernels status drajuakshayarao/arcade-gpu-model-sweep-2026-11-24` failed because the environment denied outbound access to `www.kaggle.com` (`WinError 10013`). The last persisted handoff says Version 2 was queued and had GPU/data inputs attached, but its current status cannot be confirmed. No results were collected and no training completion is claimed.

Latest complete local verification after logging: backend **99 passed**, frontend **35 passed across 12 files**, Python compileall passed, and production build passed (1,685 modules). No manual browser/security/performance testing or deployment was performed.

## Requirement source limitation

The original Infosys requirements document itself (PDF/DOCX or other identifiable source) was not present in this project workspace and was not located among this project's documentation files. An adjacent `complete_project/documentation/milestones.md` is a continuation checklist, not the original Infosys specification, so it has not been treated as a substitute. This audit covers the milestone requirements supplied in the conversation and preserved in this project checklist. Any additional requirement appearing only in the absent original document remains unaudited until that source is placed in the project.

## Development continuation ? on-demand Integrated Gradients (2026-11-25)

Implemented optional model-input attribution for newly recorded lesion analyses:

- `backend/app/arcade_ml/explain.py`: preprocesses with the same resize/normalization as inference, computes Integrated Gradients for predicted foreground logits, and creates a labeled overlay. Baseline and target are recorded; invalid, empty, or zero-attribution results are rejected.
- `backend/app/api/analysis.py`: saves the checkpoint SHA-256 on new lesion analyses and adds `POST /api/analyses/{analysis_id}/explain`. The route checks case access and image-preprocessing permission, confirms the exact checkpoint is still active, reloads the stored original image, and stores result metadata/artifact in existing JSON columns and protected artifact storage. No database migration or checkpoint modification is involved.
- `frontend/src/pages/CaseDetailPage.jsx`: adds a progress-aware optional attribution action and displays the protected image and explanatory limits in analysis history.
- Focused coverage: `backend/tests/test_integrated_gradients.py`, `backend/tests/test_analysis.py`, and `frontend/src/pages/CaseDetailPage.test.jsx` cover attribution behavior, refusal cases, API persistence/artifact response, and UI invocation.
- `docs/api_documentation.md`, `docs/database_schema.md`, `docs/user_guide.md`, and `README.md` describe endpoint, persistence, provenance checks, and scientific limits.

This does not complete clinical explainability validation. No new model evaluation, medical validation, browser testing, security testing, performance testing, or deployment was performed. Original Infosys source remains unavailable as described above.


Latest verification for this checklist update: full backend **109 passed**; focused Integrated Gradients/API/export tests **9 passed**; frontend **37 passed across 12 files**; `python -m compileall -q app tests alembic` passed; Vite build passed (1,685 modules). Database SHA-256 `90b6cdb4b78d58105b3615e470ead0d388e1c462ee06d7f8a749f5362c0b8d2e` was the pre-comparison baseline; the current post-comparison hash is recorded below. Active checkpoint SHA-256 remains `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`. Manual browser/security/performance checks and deployment remain not performed.


## Development continuation ? exact ARCADE training-label comparison (2026-11-25)

- Added `backend/app/arcade_ml/ground_truth_comparison.py`: exact filename plus SHA-256 image matching to the configured `stenosis/train` COCO set, category-26 filtering, strict dimension checks, pixel metrics, stored-component mapping, and four-panel visualization. No guessed match is permitted.
- Added `POST /api/analyses/{analysis_id}/ground-truth` in `backend/app/api/analysis.py`. It requires case access and `dataset:inspect`, reuses the persisted mask without inference/training, saves metrics and a protected visual artifact into the existing analysis JSON/artifact fields, and exposes aggregate/per-candidate results in JSON/CSV/PDF exports.
- `frontend/src/pages/CaseDetailPage.jsx` now allows authorized users to launch the comparison, shows IDs/dimensions/metrics/candidate overlap, and previews the generated panel. Tests added in `backend/tests/test_ground_truth_comparison.py` and `frontend/src/pages/CaseDetailPage.test.jsx` cover exact matching, alignment/metric errors, permissions, persistence, exports, and display.
- Exact case comparison: `case_008`, analysis `cb48c404-6a86-4d76-a167-8cec215b57e2`; dataset image `stenosis/train/images/1.png`, COCO image ID **1**, annotation file `stenosis/train/annotations/train.json`, annotation ID **98**, category ID **26**, dimensions **512 x 512**. The uploaded image and dataset image SHA-256 match (`e285e6f9515aedeb4d126182475dc43cfee8f8594ecdfa8023c9df0a97aef8e1`). Stored prediction mask dimensions align. The active checkpoint is the recorded `best_stenosis_unet_optimized.pth` with matching SHA-256 `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`.
- Metrics: TP **2,378**, FP **2,413**, FN **92**, Dice **0.655006**, IoU **0.486996**, precision **0.496347**, recall **0.962753**. Candidate **5** overlaps (2,378 of 3,100 predicted pixels, 0.767097 fraction); candidates **1, 2, 3, 4** have zero overlap. These are single-image train-label segmentation metrics, not clinical stenosis measurements or independent validation.
- A standalone visualization and machine-readable report are in `reports/ground_truth_comparison/` and detailed in [ground_truth_comparison.md](ground_truth_comparison.md). The standalone comparison was first computed read-only. The exact result was then saved through the comparison handler to the existing `case_008` analysis row and protected artifact store, with an administrator audit entry; existing prediction/result fields were retained.


### Persisted target-case update

The authorized comparison handler was invoked for analysis `cb48c404-6a86-4d76-a167-8cec215b57e2` as the owning administrator after validating the role, case identity, five-component result, recorded/current checkpoint hash, and absence of a prior comparison artifact. It added `ground_truth_comparison` to the existing result JSON, added the protected artifact mapping, and recorded an audit event. Existing image, prediction mask, candidate data, and model fields were retained. Current DB/checkpoint hashes and full-suite evidence are in the final audit.


Post-comparison current database SHA-256: `fb961ffe68413055dfab2ec678d714963b35a8cea23258d13beb90f9ddf84dcd` (196,608 bytes). The active checkpoint SHA-256 remains `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`.
