# Final project completion audit

Audit date: 2026-11-24. Scope: existing `artery-preprocessing-project`; no project recreation, destructive operation, model promotion, Kaggle resubmission, or production deployment.

## Status definitions and totals

- **Completed and verified**: implemented and covered by an appropriate automated test or recorded execution.
- **Implemented, not fully verified**: code is present, but production, browser, or real remote-output verification remains.
- **Partially implemented**: some capability exists, but a known part is incomplete or has a documented data limitation.
- **Not implemented**: no implementation exists.
- **Blocked**: completion depends on missing measurements or an external service/environment.

There are 40 applicable tasks. Development completion counts completed plus implemented-but-not-fully-verified tasks: **33 / 40 = 82.5%**. Verification completion counts completed-and-verified tasks only: **27 / 40 = 67.5%**. After adding the guarded formula helper, the task-status totals are 27 completed/verified, 6 implemented/not-fully-verified, 3 partial, 4 blocked, and 0 wholly unimplemented. Partial, absent, and blocked tasks do not count as complete. These percentages do not measure clinical validity or deployment readiness.

## Task matrix

| # | Requirement | Status | Evidence / limitation |
|---:|---|---|---|
| 1 | Registration, login, password hashing, JWT lifecycle | Completed and verified | Backend auth tests; frontend login and token tests |
| 2 | Role permissions and protected endpoints | Completed and verified | Backend authorization tests; route guard tests |
| 3 | Case CRUD, ownership, sharing, assignment, visibility | Completed and verified | Backend case-access and case tests |
| 4 | Safe upload, validation, private source-image retrieval | Completed and verified | Upload validation and access tests |
| 5 | Image preprocessing, history, original preservation | Completed and verified | Backend pipeline and frontend preprocessing tests |
| 6 | Dashboard statistics scoped to visible cases | Completed and verified | Dashboard API tests and role-specific UI tests |
| 7 | Admin user operations and audit API | Completed and verified | Role, input, activation, self-deactivation, and audit tests |
| 8 | Protected generated artifacts and PDF/CSV/JSON reports | Completed and verified | Owner/shared/assigned/outsider artifact and report tests |
| 9 | Production database migration/initialization on target environment | Implemented, not fully verified | Alembic and additive startup initialization exist; target deployment DB not exercised |
| 10 | Login and registration frontend | Completed and verified | Login component and API tests; route registration is wired |
| 11 | Nested routes, route guards, role redirects | Completed and verified | `App.test.jsx` and `ProtectedRoute.test.jsx` |
| 12 | Role-specific navigation and application shell | Completed and verified | Application route tests assert visible role links |
| 13 | Case list, create, detail and search UI | Completed and verified | Component tests; API behavior has backend tests |
| 14 | Frontend image upload | Completed and verified | Case detail UI test submits multipart upload request |
| 15 | Frontend preprocessing workflow and feedback states | Completed and verified | Loading, success, and failure component tests |
| 16 | Analysis UI, candidate details and visualizations | Completed and verified | Component tests render result fields and protected artifact requests |
| 17 | Report export interactions | Completed and verified | UI download requests and backend format tests |
| 18 | Admin users and audit-log screens | Completed and verified | Loading/data/error/empty and role/activation UI tests |
| 19 | ARCADE COCO parsing and stenosis category mask handling | Completed and verified | Dataset/COCO tests and recorded dataset audit |
| 20 | Train/validation loading and duplicate-leakage handling | Completed and verified | Loader/audit tests; routine audit excludes test split |
| 21 | Segmentation models, losses, metrics, training/checkpoint routines | Completed and verified | Unit tests and completed local experiment evidence |
| 22 | Active U-Net validation inference and application compatibility | Completed and verified | 512Ã—512 validation inference and backend analysis tests |
| 23 | ResUNet full-validation comparison | Completed and verified | Same-protocol report; worse than active baseline, not promoted |
| 24 | Attention U-Net experiment | Partially implemented | Checkpoint/report exist, but run stopped at 5 of 6 epochs |
| 25 | SMP architecture/checkpoint support | Implemented, not fully verified | Loader/notebook paths exist; no completed SMP training output |
| 26 | Kaggle Version 2 GPU training run | Blocked | Last remotely recorded state is QUEUED; live refresh failed due blocked outbound network |
| 27 | Kaggle output collection against actual remote results | Implemented, not fully verified | Collector exists; no completed Version 2 output bundle to validate |
| 28 | Candidate extraction and connected-component localization | Completed and verified | Inference/report metrics; localization quality remains weak |
| 29 | Segmentation overlays, boxes and probability heatmaps | Completed and verified | Inference artifacts and UI tests; these are not Grad-CAM |
| 30 | Diameter-based percentage narrowing | Partially implemented | Guarded formula arithmetic accepts only trusted mm inputs; image-based measurement remains unavailable because ARCADE and the active mask provide no validated lumen/reference diameters or calibration |
| 31 | Clinical stenosis severity grading | Blocked by missing measurements and validation | No valid diameter data or clinically validated grading protocol |
| 32 | Dashboard validation examples and checkpoint comparisons | Implemented, not fully verified | UI/API paths exist and preview behavior is tested; no full live-browser workflow |
| 33 | Analysis persistence, inference API, and report integration | Completed and verified | Backend analysis/export tests and recorded real-image inference |
| 34 | Setup, API, model limitations, and Windows documentation | Completed and verified | README and docs reviewed; testing guide updated |
| 35 | Production secret/CORS validation | Completed and verified | Configuration validation tests |
| 36 | Persistent storage paths and runtime initialization | Implemented, not fully verified | Paths resolve from backend settings; target production layout not exercised |
| 37 | Full browser-to-backend user journey | Implemented, not fully verified | Automated components/routes exist; user has reserved browser verification for manual testing |
| 38 | Production deployment | Blocked by external environment | No target host, production secrets, or deployment execution supplied/performed |
| 39 | Strictly untouched test holdout guarantee | Partially implemented | New routine train/validation workflows do not access test; historical integrity audit did read test files |
| 40 | Independent clinical validation on suitable data | Blocked by missing external data/process | Requires a clinically annotated, calibrated independent cohort and validation protocol |

Numerical helper tests include reference/minimum values of 4/2 mm (50%), 4/4 mm (0%), 4/3 mm (25%), and 5/1 mm (80%); these are synthetic arithmetic checks, not image measurements. No task is classified as wholly not implemented: unavailable clinical features are classified as blocked because their required inputs and validation are absent, rather than being approximated from lesion boxes.

## Weighted completion

Weights reflect project risk and importance. Each module's development and verification fractions use its task counts above; the weighted result is the sum of module fraction Ã— module weight.

| Module | Weight | Development complete | Verified complete |
|---|---:|---:|---:|
| Backend APIs, authorization, and data services (tasks 1â€“9) | 25% | 8/9 = 88.9% | 8/9 = 88.9% |
| Frontend application and routing (tasks 10â€“18) | 20% | 9/9 = 100% | 9/9 = 100% |
| Dataset and model/training (tasks 19â€“27) | 25% | 7/9 = 77.8% | 5/9 = 55.6% |
| Analysis, visualization, and clinical measurement (tasks 28â€“33) | 15% | 4/6 = 66.7% | 3/6 = 50.0% |
| Documentation, operations, and external validation/deployment (tasks 34â€“40) | 15% | 4/7 = 57.1% | 2/7 = 28.6% |

Weighted development: `0.25Ã—0.889 + 0.20Ã—1 + 0.25Ã—0.778 + 0.15Ã—0.667 + 0.15Ã—0.571 = 80.2%`.

Weighted verification: `0.25Ã—0.889 + 0.20Ã—1 + 0.25Ã—0.556 + 0.15Ã—0.500 + 0.15Ã—0.286 = 67.9%`.

## Measurements and model status

The diameter formula is `((reference diameter âˆ’ minimum lumen diameter) / reference diameter) Ã— 100`. The source annotations describe stenosis lesions with polygons/boxes; they do not supply lumen contours, comparable reference and minimum lumen diameters, physical pixel spacing, or validated anatomical reference segments. Therefore percentage narrowing and severity remain null. A future implementation needs calibrated lumen measurements from the same vessel segment (or a validated imaging measurement method), unit checks, a clinically approved reference-segment protocol, and independent validation. Lesion dimensions and model scores cannot substitute.

The active checkpoint is `backend/checkpoints/best_stenosis_unet_optimized.pth`, architecture `legacy_unet`, 256 input. On the recorded full 200-image validation evaluation it has macro Dice 0.43169, macro IoU 0.29631, and global Dice 0.45558 at threshold 0.55. ResUNet scored macro Dice 0.34666 and macro IoU 0.22766; it was not promoted. Attention U-Net scored macro Dice 0.27833 and macro IoU 0.17646 after an interrupted 5/6 epoch run; it was not promoted. Candidate IoU-0.30 TP/FP/FN for the active model were 108/497/298, indicating weak localization despite the better pixel-overlap metrics.

Kaggle Version 2 was last confirmed QUEUED in the stored remote metadata/handoff. A read-only `kaggle kernels status` attempt during this audit could not reach `www.kaggle.com` because network access is denied in this environment. No GPU, execution progress, new output, or training metric is asserted. No kernel or dataset was resubmitted.

## Automated verification and preservation

Latest automated run after the guarded-measurement and report/UI changes: backend pytest **81 passed**, Python compilation passed, frontend Vitest **32 passed across 11 files**, and Vite production build passed. No manual browser test or deployment was performed. See [testing.md](testing.md) and [model_validation_report.md](model_validation_report.md).

The pre/post audit fingerprint command used SHA-256 over sorted relative paths, file sizes, and each file SHA-256. Counts, bytes, and fingerprints were identical before and after the audit for:

| Protected path | Files | Bytes | Tree SHA-256 |
|---|---:|---:|---|
| `backend/uploads` | 6 | 9,913,751 | `91bf0993827fab5a8fb9a4fc5ef84a7d4c9b58c3a22e2cdae356ec8b6c755adf` |
| `backend/processed` | 21 | 5,347,112 | `b6ddb97ded6f376ac80eb30faeef5249926869cf1a6c8dc1048fee5a2891fa16` |
| `backend/analysis` | 4 | 1,010,025 | `a2ac1f58e0ee4f4f656e3ca9a07c2740627b4706250d6cb3c3f1f40feab22c30` |
| `kaggle_upload/arcade_training_data` | 2,406 | 412,473,222 | `88f09a134d0d5b94ae527dc8b96f77bd9f9a782597fc5f5cabb5e74e13802dc5` |
| `../stenosis` (source ARCADE) | 1,503 | 203,603,986 | `2b98e10e74145aaff3353a2589379d7d0180f6affcad7e2596293a8ac12f5fd8` |
| `../syntax` (source ARCADE) | 3,003 | 293,389,478 | `629c7937b9e210b3a9a3753dc885dd644d48bc66b4c49356dd6429e04a78e2ec` |

SQLite SHA-256: `90b6cdb4b78d58105b3615e470ead0d388e1c462ee06d7f8a749f5362c0b8d2e` (180,224 bytes). Active checkpoint SHA-256: `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d` (7,716,521 bytes). Both match the required known values.

## Remaining manual and external work

1. Complete the browser checklist in [demonstration_checklist.md](demonstration_checklist.md), including login, role-restricted routes, case create/upload/preprocess/analyze, protected files, exports, and admin screens.
2. Wait for Kaggle to leave QUEUED; then collect outputs, validate logs/metrics on validation only, and compare with the active baseline. Do not promote unless the improvement is measured and inference-compatible.
3. Do not implement narrowing/severity until calibrated lumen measurements and an approved validation protocol are available.
4. Configure actual production secrets, HTTPS origin, persistent storage/database, backups, and target deployment; then run a deployment smoke test.
5. Keep the historical test-split integrity read documented; new training/model selection remains train/validation-only.

## Separate SYNTAX vessel-region experiment (2026-11-24)

A COCO audit found SYNTAX/train and SYNTAX/val polygon labels for coronary artery segment categories 1â€“25; stenosis/category 26 remains the separate lesion target. There are no lumen-caliper/reference-diameter or calibration fields in the COCO image/annotation records. The polygon regions are useful for a distinct experimental vessel-segment model but do not establish a complete lumen-wall boundary or valid diameter measurements. Official task definitions also separate vessel segmentation and stenosis detection ([ARCADE tasks](https://arcade.grand-challenge.org/tasks/), [dataset paper](https://doi.org/10.1038/s41597-023-02871-z)).

A separate task-tagged training mode and validation-only evaluator were added. The evaluator unions the annotated SYNTAX polygons, chooses a threshold using syntax/val macro Dice, and emits JSON, per-image CSV, and visual examples. It never opens test. The model is experimental, is not connected to lesion inference, and does not call the guarded stenosis formula. No automatic diameter/narrowing result is available without calibrated lumen boundaries and a valid reference segment. See [vessel_segmentation_experiment.md](vessel_segmentation_experiment.md) for commands and limitations.

### Experiment results and interpretation

The completed five-epoch CPU U-Net run used 995 unique SYNTAX training images (five duplicate filenames excluded) and 200 validation images. With 256 input, 8 base channels, BCE+Dice/AdamW and seed 20261124, the full-resolution validation evaluator selected threshold 0.75 and measured macro Dice 0.74255, macro IoU 0.59695, global Dice 0.74530, precision 0.73356, recall 0.75742, and specificity 0.98977. These metrics are against the union of annotated SYNTAX segment polygons only.

A completed five-epoch ResUNet run selected threshold 0.65 and achieved validation macro Dice 0.73742 / IoU 0.59165 (global Dice 0.74287, precision 0.72829, recall 0.75805, specificity 0.98949); U-Net was slightly higher on macro overlap. Both thresholds are validation-selected and these remain exploratory segment-polygon metrics, not lumen scores. The new tests include the annotation-union loader and validation-only evaluator; all 83 backend tests and Python compilation passed. Frontend tests passed 32/32 across 11 files, and the production build passed. See [experiment report](vessel_segmentation_experiment.md).


## Final verification update (2026-11-25)

The separate SYNTAX U-Net and full ResUNet experiments completed. The final report and exact commands are in [vessel_segmentation_experiment.md](vessel_segmentation_experiment.md). An additional epoch-3 ResUNet checkpoint from an interrupted earlier attempt remains in `backend/checkpoints/syntax_resunet8_experiment.pth`; it was not used as the completed comparison or promoted. The completed ResUNet run used a distinct filename.

Verification after these changes: backend pytest **83 passed**, frontend Vitest **32 passed in 11 files**, Python compileall passed, and the frontend production build passed. No frontend/backend application integration was added for experimental segment-region predictions because they are not validated lumen measurements. No manual browser testing or deployment was performed.

Post-run preservation check: database SHA-256 remains `90b6cdb4b78d58105b3615e470ead0d388e1c462ee06d7f8a749f5362c0b8d2e`; active lesion U-Net SHA-256 remains `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`. All pre-existing lesion experiment checkpoint and threshold-file hashes also match the recorded baseline. Protected path file counts and byte totals are unchanged: uploads 6 / 9,913,751; processed 21 / 5,347,112; analysis 4 / 1,010,025; staged train/validation bundle 2,406 / 412,473,222; source stenosis 1,503 / 203,603,986; source syntax 3,003 / 293,389,478. The experimental commands read the source labels and wrote only new experiment checkpoints/reports; they did not alter original dataset files, application storage, database, or Kaggle configuration.

Annotation inventory clarification: the SYNTAX split also supplies binary PNG masks (1,000 train, 200 validation, 300 test). On validation, those masks have mean IoU 0.911 against the COCO polygon union, so they are related vessel-region targets but not identical; the reported experiments used the COCO polygon union. Test annotation schema only was inspected for available fields. No test prediction, score, training, threshold selection, or model selection was performed. No mask or COCO metadata contains physical spacing, diameter measurements, or a reference-segment label.


## Current vessel/lumen investigation status (addendum; not included in the historical 40-task percentages)

| Item | Status | Evidence / blocker |
|---|---|---|
| Inspect COCO and supplied SYNTAX binary-mask formats | Completed | Train/validation/test formats audited; validation mask-to-polygon mean IoU 0.911; metadata has no spacing, diameter, or reference-segment fields. Test schema only was inspected, with no test scoring or use for selection. |
| Separate experimental SYNTAX vessel-region model | Implemented and evaluated | U-Net and ResUNet checkpoints/reports are separate from active lesion inference; validation-only threshold selection and visual overlays are saved. U-Net was slightly higher on polygon-region macro overlap. |
| Validated complete lumen-wall segmentation | Blocked by label scope | ARCADE labels anatomical SYNTAX segment regions, not validated inner-lumen contours at stenosis and reference cross-sections; some visible non-SYNTAX branches are outside the label protocol. |
| Automatic diameter/narrowing integration from images | Blocked; guarded helper remains | No validated lumen boundaries, physical pixel calibration, or reference segment; no stenosis percent or severity is emitted from the experimental output. |
| Promote the experimental model | Not applicable / not promoted | It has different segment-region semantics and cannot replace the active lesion checkpoint or produce a valid narrowing measurement. |


## Optional vessel-region application integration addendum

Implemented an experimental mode in the existing case analysis page and API, leaving lesion analysis selected by default. The experimental checkpoint is separately selected and must have its validation-only threshold report. The mode stores its type and outputs in the existing JSON result, returns protected mask/overlay/centerline/cross-section/heatmap artifacts, appears in analysis history, and exports pixel-width fields in JSON/CSV/PDF. No database schema change was made. API authorization follows the existing accessible-case permission check and generated artifacts use the existing protected artifact route.

A pixel-width helper now finds connected regions, skeletonizes them, estimates local direction using PCA, and samples perpendicular cross-sections. Quality guards omit small/ambiguous/edge-clipped sections. These widths are explicitly pixel-only SYNTAX vessel-region estimates and are not converted to lumen diameters or sent to the guarded stenosis formula. A 512x512 SYNTAX validation image produced 11 regions and 24 sampled widths (minimum 3.5 px); this is a smoke check of code execution, not measurement validation.

Continuation-specific status: three of six scoped items are implemented and automated-verified (pixel-width routine/visualization, optional app/API mode, persistence/export/authorization path); three remain blocked or external (validated lumen boundary model, calibrated image-based stenosis measurement, and manual browser/deployment verification). This scoped development/verification percentage is 3/6 = 50% each; it is separate from the historical project-wide 40-task percentages above.

Latest verification after this integration: backend pytest **87 passed**, frontend Vitest **33 passed across 11 files**, Python compilation passed, and Vite production build passed. The active checkpoint and database were rechecked against their required SHA-256 values; uploads/processed/analysis and original dataset/staged-bundle inventories match prior file counts and byte totals. No manual browser test or deployment was performed.

## Final continuation verification correction

Following the last PDF export assertion and diagonal-orientation test, the final backend suite result is **89 passed**; Python compilation passed. The final frontend suite remains **33 passed in 11 files**, and the final Vite production build passed. The earlier continuation addendum's backend count (87) is superseded by this latest total. The feature-specific completion estimate remains 3/6 implemented/verified = 50%; it excludes the historical project-wide 40-task score.

## Lumen-diameter / stenosis acceptance audit (2026-11-25)

Both requirements are blocked: the current lesion model predicts lesion regions; the SYNTAX mode predicts annotated vessel regions and only offers uncalibrated pixel widths. The guarded formula remains unavailable without calibrated validated lumen and reference measurements. The DICOM loader stores PixelSpacing metadata, but the current analysis path does not use it; the current database upload records are five PNG images with no spacing. See [lumen measurement audit](lumen_measurement_completion_audit.md) for the detailed code path, external data review, and exact unblock requirements. No model or calibration integration was attempted without suitable labels/validation data.

## Project-wide requirement reconciliation (2026-11-25)

The expanded milestone and end-to-end workflow checklist, including code paths, statuses, evidence, unverified/manual tasks and exact lumen-data blockers, is in [project_requirement_checklist.md](project_requirement_checklist.md). Original Milestone 1–4 source documents are not present in this workspace; the checklist therefore reconciles the supplied task descriptions, README, existing docs and historical 40-task matrix. Latest automated counts are backend **89 passed**, frontend **33 passed in 11 files**, Python compileall passed, and production build passed; details are in [testing.md](testing.md). No manual browser test or deployment was performed.

### DICOM PixelSpacing provenance continuation (2026-11-25)

M1.6's feasible metadata handling was completed: validated DICOM PixelSpacing provenance is carried into analysis history, UI, and reports without being used for diameter calculations. Invalid/missing spacing is explicit. The new full-suite result is backend **93 passed**, frontend **33 passed in 11 files**, Python compileall passed, production build passed; see [testing.md](testing.md) and the detailed checklist entry. The generated DICOM parser test is synthetic; no real DICOM measurement validation was performed. M3.4–M3.6 remain blocked.

### ARCADE split inventory continuation (2026-11-25)

M1.2's dataset inspection now exposes local stenosis/SYNTAX train/validation COCO counts and test image counts without opening test annotations. Read-only local inventory is in [project_requirement_checklist.md](project_requirement_checklist.md). Current full-suite results are backend **94 passed**, frontend **35 passed in 12 files**, Python compileall passed, and production build passed. Dataset tests use isolated temporary files; the actual dataset was only read. M3.4–M3.6 remain blocked as documented.

### Additive migration continuation (2026-11-25)

M1.7's fresh and legacy-partial SQLite migration paths are now covered with disposable databases. A concrete issue was fixed: the initial revision now preserves an existing unstamped user table, and revision 0004 creates missing model tables. The app database was not migrated. Latest full verification: backend **96 passed**, frontend **35 passed in 12 files**, Python compileall passed, production build passed. DB and active checkpoint hashes remain the protected values listed above, and uploads, processed images, analysis artifacts, staged bundle and source dataset counts/bytes remain unchanged. See [project_requirement_checklist.md](project_requirement_checklist.md) for migration limitations.

### Configurable local logging and Kaggle status check (2026-11-25)

M4.8 now has a configurable local rotating-file sink with bounded size/retention and tests. Production centralized logging remains unconfigured. Kaggle CLI status retrieval failed with `WinError 10013` because outbound access to Kaggle is denied; the last persisted handoff says Version 2 was queued. The existing kernel was not changed, and no output was collected. Current full verification: backend **99 passed**, frontend **35 passed in 12 files**, Python compileall passed, build passed. Manual browser/security/performance tests and deployment remain unperformed.


## Project-wide continuation update ? 2026-11-25

### Work completed in this continuation

- Added optional Integrated Gradients attribution for new lesion analyses. The input path uses the inference resize/normalization convention; the target is the mean lesion logit over predicted foreground. The protected artifact and method/steps/limits are stored using existing analysis JSON columns. JSON, CSV and PDF exports include attribution metadata.
- New analyses record checkpoint SHA-256; the loaded-model cache is keyed by content hash and verifies the checkpoint before/after loading and around inference. The explanation endpoint requires accessible-case permission plus image-preprocessing permission and runs only if the active checkpoint hash still matches. Legacy records without provenance, changed/missing checkpoints, unsupported modes, empty foreground, and invalid maps are refused explicitly.
- Added backend unit/API/export and frontend interaction coverage, updated API/schema/user/setup documentation, and created a project report and slide outline. No DB migration, checkpoint replacement, dataset edit, case-record edit, or Kaggle submission was performed.

### Current automated verification

Backend: **103 passed**. Frontend: **36 passed across 12 files**. Python compileall passed. Production frontend build passed (1,685 modules). These are automated regression checks only; they do not satisfy manual browser, dedicated security, performance, medical-validation, or deployment work.

### Milestone status summary

- **Milestone 1:** dataset inventory/COCO parsing, preprocessing, DICOM metadata provenance, auth/roles, case/image workflows, and additive fresh/legacy migration support are implemented. The original Infosys specification was not present in this workspace. The application database was not migrated. Historical test-split audit exposure is irreversible; routine paths remain train/validation only.
- **Milestone 2:** model, loader, training/evaluation and local inference are implemented; the active model remains unchanged. Kaggle Version 2's last persisted state is QUEUED, but live status is unverified because the previous CLI request was denied outbound access (`WinError 10013`). No training results were collected or asserted.
- **Milestone 3:** lesion candidates, overlays/probability maps, optional Integrated Gradients, and an exact-match train-label comparison for the target case are implemented; SYNTAX remains experimental vessel-region/pixel-width output. Actual lumen boundaries, diameter in mm, automatic stenosis percentage and clinical severity remain blocked by absent validated lumen labels, angiographic calibration, and reference measurements. No real-image clinical attribution validation was performed.
- **Milestone 4:** dashboard/admin/history/reports/model metadata comparison/API flows/local rotating logs and documentation are implemented. Manual browser verification, security review, performance testing and deployment are not completed. Deployment also needs target infrastructure and production operational settings.

### Preservation verification at the end of the previous continuation (before the case comparison update)

Read-only SHA-256 at that point: application database `90b6cdb4b78d58105b3615e470ead0d388e1c462ee06d7f8a749f5362c0b8d2e` (180,224 bytes); active checkpoint `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d` (7,716,521 bytes). These match the previously recorded hashes. `backend/logs` is absent; tests used isolated temporary storage. Existing ARCADE source and staged bundle were not written. Earlier protected inventory counts/bytes remain the last recorded baseline; this continuation did not modify those locations.

### Remaining blockers and user-provided inputs

1. Provide the original Infosys requirements source to reconcile requirements exclusive to that file.
2. For lumen/stenosis research, provide authorized angiograms, valid physical calibration and transform provenance, adjudicated inner-lumen contours/diameters at lesion and reference segments, and a defensible reference protocol with independent subject-level validation.
3. The existing Kaggle run must actually complete and yield logs/checkpoints before its collector and validation-only comparison can run. Do not duplicate its submission.
4. Manual browser, dedicated security/performance checks, and deployment remain user-reserved; deployment additionally requires a target environment.


## Case-specific ARCADE ground-truth comparison (2026-11-25)

A strict-match comparison workflow was implemented and exercised against the existing five-candidate lesion analysis for uploaded `case_008`. The uploaded `1.png` exactly matches `stenosis/train/images/1.png` by SHA-256; its COCO record is image ID 1, 512 x 512, in `stenosis/train/annotations/train.json`, with annotation ID 98/category 26. The persisted prediction mask is aligned and was evaluated without rerunning the model. The analysis checkpoint hash matches the current active U-Net. Results: TP 2,378, FP 2,413, FN 92; Dice 0.655006; IoU 0.486996; precision 0.496347; recall 0.962753. Candidate 5 overlaps the label (2,378 pixels of 3,100); candidates 1, 2, 3, and 4 do not overlap. The four-panel image and JSON report are saved under `reports/ground_truth_comparison/`; see [case comparison report](ground_truth_comparison.md). These train-image pixel metrics do not imply clinical stenosis or lumen measurement.

The application has an authorized `POST /api/analyses/{analysis_id}/ground-truth` path and case UI to persist/display this data additively. The comparison was first computed read-only, then the user-requested comparison handler was invoked for the exact stored analysis as its owning administrator. It added the comparison payload, artifact mapping, protected visualization and audit event without replacing prior analysis fields or the original prediction mask.


### Verification and preservation after saving the case comparison (2026-11-25)

Full backend: **109 passed**. Full frontend: **37 passed across 12 files**. Python compileall passed. Production build passed (1,685 modules). The target existing analysis now includes the ARCADE comparison and a protected artifact; this was the one intentional application DB change. The existing case/image/prediction fields remain intact. The source dataset image/annotation were read only; upload bytes were compared but not modified. Active checkpoint remains unchanged. Actual post-update database and checkpoint hashes are recorded below after the final read-only verification.


Post-comparison database SHA-256 is `fb961ffe68413055dfab2ec678d714963b35a8cea23258d13beb90f9ddf84dcd` (196,608 bytes). The comparison added its expected JSON fields, artifact mapping, artifact file, and one audit row; all other identified existing case/image/analysis fields were retained. Active checkpoint SHA-256 remains `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d` (7,716,521 bytes).

## Lumen diameter continuation (2026-11-25)

Added `backend/app/arcade_ml/lumen_measurement.py`, an isolated geometry-only consumer for expert-validated lumen masks and lesion/reference ROIs. It measures perpendicular pixel cross-sections along a morphological centerline, selects the minimum within the validated lesion ROI, uses the median of validated reference sections, can convert widths with explicitly verified anisotropic DICOM image-plane spacing, and delegates the percent formula to the existing validation gate. It can render supplied contours, centerline and calipers. It is not an automatic lumen segmenter and is not connected to ordinary analysis because the project lacks suitable lumen annotation inputs. Normal API results remain unavailable. No real angiogram was validated and no clinical measurement claim is made.

Added synthetic geometry tests and strengthened API/UI tests that current lesion inference does not return candidate-box width as diameter and that reported spacing cannot pass calibration gates. The synthetic percentage example is a unit fixture, not a project result. Verification: backend **120 passed**; Python compileall passed; frontend **37 passed across 12 files**; Vite production build passed (1,685 modules). No manual browser, medical validation, security, performance, or deployment work was performed. Read-only preservation checks: the active checkpoint remains SHA-256 `981A98A7AB1CEEE190D1D0C89C45CDEB37DD27B49741F3FFDA1487D1F38D288D`; the SQLite database SHA-256 remains `FB961FFE68413055DFAB2EC678D714963B35A8CEA23258D13BEB90F9DDF84DCD`, matching the post-comparison value. Automated tests use in-memory SQLite and temporary storage. No dataset, upload, processed image, analysis artifact, checkpoint, database record, or Kaggle setting was changed in this continuation. Actual automatic lumen segmentation and real-case mm/stenosis remain blocked by missing expert-labeled calibrated invasive angiography.

## Continuation: Infosys requirements crosswalk and professional application shell (2026-11-25)

The original project PDF supplied by the user (`C:\Users\aksha\Downloads\Artery_Segmentation_and_Stenosis_Detection_Using_Advanced_DL_Techniques (1).pdf`) is treated as the requirements source. The current user-pasted continuation prompt is treated as the implementation instruction and controls its stated exclusions: no lumen/diameter work, checkpoint retraining/replacement, manual browser testing, dedicated security/performance testing, or deployment. Requirement groups and their code evidence are cross-referenced in the [master checklist](project_requirement_checklist.md).

The existing app received a responsive navy/light interface shell and navigation for Dashboard, Cases, upload, preprocessing, analysis history, reports, model comparison, dataset inspection, user management, audit logs, and profile. New pages call the existing APIs: upload uses the authorized case list/upload endpoints; history queries scoped analysis records; reports request case-scoped PDF/CSV/JSON; model comparison displays checkpoint metadata and saved evaluations only. Dashboard now includes recent visible cases and links to case creation, upload and history. Preprocessing/profile forms expose permission, busy and validation states. Existing case analysis and inference were retained.

Automated verification: backend **120 passed**; frontend **50 passed across 17 files**; `python -m compileall -q app tests alembic` passed; Vite production build passed with **1,689 modules**. The first frontend run found stale dashboard test assumptions after the shared shell took over the page title and a new `/api/cases` request was added; fixtures were corrected, recent-case/profile tests were added, and the final complete suite passed. No live browser/API flow was tested.

Files changed are itemized in [the master checklist](project_requirement_checklist.md). No backend source or migration was changed. No original dataset, checkpoint, database record, upload, processed image or analysis artifact was intentionally modified by this continuation. Previously recorded post-comparison database SHA-256: `fb961ffe68413055dfab2ec678d714963b35a8cea23258d13beb90f9ddf84dcd`; active checkpoint SHA-256: `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`. No Git metadata exists. These values are prior recorded fingerprints; the present continuation did not recalculate them.

Remaining limitations: actual lumen boundaries and image-based physical stenosis remain blocked; Kaggle output collection remains contingent on the existing run completing (no live refresh during this UI task); notification/clinical alert policy, model promotion/rollback registry, centralized monitoring sink, and container/cloud deployment are absent or incomplete. Manual browser/accessibility review, dedicated security and performance tests, and deployment remain for the user. This audit does not claim 100% completion or clinical validity.


## Continuation: remaining locally actionable requirements (2026-11-25)

The source PDF remains the requirement reference; the latest user task controls explicit exclusions. Local rotating logs, admin audit records, a database readiness probe, and privacy-minimal request/latency logging are implemented. The database probe returns 503 on failure and does not leak database exception text. Audit events can be refreshed in the admin UI, and report-download URLs are retained for one second so the browser has time to begin consuming the Blob.

Admin user management now prevents deactivation or demotion of the last active administrator. No model registry promotion/rollback was added: the current model architecture exposes a read-only checkpoint directory comparison and an environment-configured active checkpoint; no candidate has a verified improvement over the baseline. Switching the active model would change application outputs and is not justified without demonstrated validation improvement; no promotion was performed. Clinical notifications/alerts were not fabricated because validated severity measurements are unavailable. Central log shipping remains unconfigured because there is no supplied collector endpoint, deployment environment, or credential/configuration. The local health and telemetry work is not claimed as centralized monitoring.

Verification after these changes: backend **123 passed**, frontend **51 passed across 17 files**, Python compileall passed, and Vite production build passed (1,689 modules). The database was not migrated or modified; automated API tests use in-memory SQLite and temporary storage. No checkpoints were opened for writing, no training was run, and no dataset or upload operation was performed. The active checkpoint SHA-256 remains `981a98a7ab1ceee190d1d0c89c45cdeb37dd27b49741f3ffda1487d1f38d288d`; the SQLite database SHA-256 remains `fb961ffe68413055dfab2ec678d714963b35a8cea23258d13beb90f9ddf84dcd`.

Remaining manual/external requirements: configure a centralized log collector/monitoring environment; provide a reviewed model registry/promotion policy and validated candidate before enabling promotion; define a nonclinical operational notification policy if desired by the project owner; perform browser/accessibility, dedicated security and performance testing; and deploy to an identified target. No manual testing or deployment is claimed.
