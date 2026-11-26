# Artery Segmentation Research Application — Project Report

Report date: 2026-11-25

## Abstract

This project is a local research application for managing angiography cases, preprocessing images, running segmentation models, reviewing candidate regions, and exporting analysis records. It integrates a React frontend with a FastAPI backend and SQLite-backed case/authentication system. An optional Integrated Gradients attribution view has been added for newly recorded lesion analyses, with checkpoint identity safeguards. The application does not provide a clinically validated stenosis diagnosis, lumen diameter, or stenosis percentage.

## Problem and scope

The development objective is to support dataset-aware artery lesion segmentation and a reviewable case workflow. The system accepts PNG/JPEG and single-frame DICOM images, retains originals in private storage, maintains cases and access permissions, records preprocessing and analysis history, and exposes reports. Experimental SYNTAX segmentation is isolated from the active lesion model. Clinical lumen measurement is explicitly out of scope until suitable annotations, calibration, reference measurements, and independent validation are available.

## Requirements and source status

The workspace checklist represents the milestone requirements supplied to the project. The original Infosys requirements document was not found in the project workspace, so requirements present only in that missing source cannot be certified. See [project requirement checklist](project_requirement_checklist.md) for task-by-task code paths and statuses. Manual/browser verification, security review, performance testing, and deployment are intentionally not claimed complete.

## System architecture

- React/Vite UI: login, protected routes, dashboard, case CRUD, uploads, preprocessing, analysis history, admin screens, comparison views and exports.
- FastAPI API: authentication and permission dependencies, case workflows, private file access, inference, protected generated artifacts, audit records, reports and dashboard statistics.
- SQLite persistence: users, cases, grants, uploads, preprocessing runs, analyses and audit events. Alembic is additive for missing tables; it does not reconcile arbitrary existing columns.
- ML: ARCADE COCO parsing, lesion masks, U-Net-family architectures, training/evaluation utilities, checkpoint loading, candidate extraction and separate SYNTAX vessel-region experiment.
- Storage: configured private upload, processed, analysis, checkpoint, dataset, and reports directories. Existing data is preserved.

See [architecture](architecture.md), [database schema](database_schema.md), and [API documentation](api_documentation.md).

## Dataset and annotation semantics

The application uses ARCADE stenosis category-26 lesion polygons and separate SYNTAX artery-region annotations. These labels do not trace the inner contrast-filled lumen wall. Routine training and model selection use train/validation data; test is a holdout. A documented train/validation duplicate is excluded from future training where detected. Historical audit activity that opened test files cannot be undone. Dataset counts and known overlap are listed in the project checklist and dataset/model audit documents; counts are inventory, not performance evidence.

## Implemented application features

Authentication, role/permission controls, case ownership/sharing/assignment, source image upload and protected retrieval, preprocessing and history, segmentation inference, candidate localization, overlays and heatmaps, optional Integrated Gradients, analysis history, PDF/CSV/JSON exports, dashboard metrics, model metadata/validation comparison, admin user/audit views, additive database initialization/migrations, configurable rotating local logs, and Windows setup guidance are present. Exact status and evidence are in the master checklist.

Integrated Gradients is computed on demand against the same checkpoint hash that was recorded when a new lesion analysis ran. Legacy analyses without provenance and analyses whose checkpoint has since changed are refused. The attribution is relative input sensitivity and is not medically validated.

## Model and evaluation results

No new model was trained or selected in this continuation. Existing validation measurements and experiment results remain in [model validation report](model_validation_report.md) and [SYNTAX vessel experiment](vessel_segmentation_experiment.md). Those results use lesion/region annotation semantics and must not be interpreted as lumen segmentation quality. The active U-Net checkpoint was not modified. The last recorded Kaggle Version 2 state was queued; fresh status retrieval had been blocked by local outbound-network policy, so no current execution or output is claimed.

## Clinical measurement and limitations

The current lesion model segments lesion regions; the SYNTAX experiment predicts broad vessel-region masks and pixel widths. Neither provides validated lumen boundaries. PixelSpacing provenance is retained for DICOM where present, but its angiographic calibration and transformation suitability are not established. Therefore lumen diameters in millimetres, percentage narrowing, and clinical severity remain unavailable. No bounding box, polygon area, pixel width, or confidence score is substituted for lumen diameter. The guarded formula helper is not fed fabricated measurements.

## Verification and preservation

Automated checks and their current exact results are recorded in [testing.md](testing.md) and the latest continuation entry in [final completion audit](final_completion_audit.md). They are regression checks, not the separately reserved manual testing milestone. The active checkpoint and application database hashes and protected-data inventory are recorded in the final audit. No original ARCADE data, user records, uploads, processed images, prior analyses, or model artifacts were intentionally changed.

## Remaining work

1. Provide the original Infosys requirements document to audit any requirements not present in the project checklist.
2. Obtain appropriately licensed angiograms with validated inner-lumen contours or QCA measurements, pixel calibration/transform provenance, and reference-segment annotation to unblock diameter and stenosis work.
3. Verify the existing Kaggle kernel and retrieve outputs only after it reports completion.
4. The user performs the separately reserved browser, security, performance and deployment tasks in the project handoff.

## Setup and handover

Windows setup, backend/frontend commands, database behavior and checkpoint configuration are in the root [README](../README.md). The [user guide](user_guide.md) describes case analysis, exports and non-clinical interpretation.
