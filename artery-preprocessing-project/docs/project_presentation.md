# Project Presentation — Artery Segmentation Research Application

Prepared 2026-11-25. This is a slide-by-slide presentation outline; it contains no fabricated clinical images or results.

## Slide 1 — Title

**Artery Segmentation Research Application**  
ARCADE lesion segmentation, case management, and review workflow.

## Slide 2 — Motivation and scope

- Provide a maintainable research workflow for angiography images.
- Connect image upload, preprocessing, model inference, visual review, analysis history, and exports.
- Outputs support research review; they are not diagnosis or treatment recommendations.

## Slide 3 — Application architecture

- React/Vite frontend and FastAPI API.
- SQLite persistence with additive migrations.
- Private upload, processed-image and analysis-artifact storage.
- U-Net-family segmentation and separate experimental SYNTAX vessel-region mode.

## Slide 4 — Data and labels

- ARCADE stenosis annotations identify lesion regions (category 26).
- SYNTAX annotations represent artery regions.
- Neither label set traces validated inner lumen boundaries.
- Test data is a holdout for routine training and selection.

## Slide 5 — User workflow

- Authenticate and create/access a case.
- Upload PNG/JPEG or a supported single-frame DICOM.
- Preprocess while preserving the original.
- Run lesion or explicitly experimental vessel-region analysis.
- Review protected artifacts and export JSON, CSV, or PDF history.

## Slide 6 — Segmentation and review

- Model mask, lesion candidates, overlay, boxes, probability map.
- On-demand Integrated Gradients input attribution is available for new lesion analyses when the checkpoint hash still matches.
- Attribution is model sensitivity visualization, not clinical confidence or validated explanation.

## Slide 7 — Evaluation

- Existing validation metrics and experiment details are in `model_validation_report.md` and `vessel_segmentation_experiment.md`.
- Reported metrics correspond to annotation semantics and do not validate lumen segmentation.
- No new training or model selection was performed in this continuation.

## Slide 8 — Why automatic narrowing is unavailable

- The active model predicts lesion regions, not lumen contours.
- SYNTAX predictions are vessel regions, not inner-wall boundaries.
- Pixel spacing alone does not establish angiographic physical calibration.
- No valid reference-segment measurement/annotation is available.
- The application reports “Unable to calculate”; no severity grade is fabricated.

## Slide 9 — Preservation, operations, and status

- Existing database, uploads, datasets, and active checkpoint are preserved.
- Configurable local rotating logs and Windows setup instructions are included.
- Kaggle completion remains unverified; no output is claimed.
- Automated verification is reported separately from manual browser/security/performance/deployment work.

## Slide 10 — Next steps

- Supply the absent original Infosys specification for full requirements reconciliation.
- Obtain calibrated, annotated lumen data and a reference protocol for valid diameter/stenosis research.
- Verify the existing Kaggle run's actual status and retrieve outputs only after completion.
- Complete user-reserved manual testing and deployment in the target environment.
