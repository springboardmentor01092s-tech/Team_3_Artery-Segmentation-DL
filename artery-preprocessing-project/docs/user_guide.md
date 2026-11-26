# User guide

## Roles

- **Researcher** (default registration): own cases, upload, preprocess.
- **Radiologist**: same operational case workflow.
- **Data scientist**: case workflow plus dataset summary.
- **Administrator**: all of the above, user management, audit logs, all cases.

## Typical demonstration

1. Register a researcher (or sign in as the bootstrapped administrator).
2. Create a synthetic case ID such as `DEMO-CTA-001`.
3. Upload a PNG from `data/sample_images` or any de-identified test image.
4. Open **Preprocessing**, choose operations, and start.
5. Confirm **Original Image** and **Preprocessed Image** labels.
6. Re-open the case and confirm history plus unchanged original dimensions/file.
7. On the case page, run segmentation and review the predicted binary mask, overlay, candidate boxes, and probability heatmap.
8. Use PDF, CSV, or JSON to export the current case's analysis history.

## Application navigation and workflow notes

- **Dashboard** shows database statistics in the account's authorized scope, recent cases and analyses, and available model information. Its shortcuts lead to case creation and upload.
- **Image upload** requires an existing accessible case and upload permission. PNG/JPEG previews remain local before the user submits; single-frame DICOM is accepted for backend validation but is not previewed in the browser. Default client guidance is 20 MiB; the server enforces its configured upload limit and validates content.
- **Analysis history** lists the latest records accessible through the API and supports case/ID/model text search and analysis-mode filtering. Open a case to inspect the corresponding artifacts.
- **Reports** selects an accessible case and requests PDF, CSV, or JSON from the case-scoped API. Export only includes records the server actually has for that case.
- **Model comparison** is read-only. It displays saved checkpoint metadata and existing validation evaluations; it does not train models, select a checkpoint, or manufacture missing scores.
- Navigation hides links based on role/permission, and nested route guards restrict dataset/admin pages. Backend checks remain authoritative; confirm end-to-end behavior during manual browser testing.
- **Audit logs** can be refreshed to retrieve events created since the page was opened. The API prevents an administrator from deactivating or demoting the final active administrator; an attempted change is rejected with an explanatory error.

The workspace was visually restyled with a responsive navy sidebar, compact top bar, light work area, role indicator, and mobile navigation toggle. Responsive rendering, keyboard flow, contrast and actual browser downloads still require manual review.

Segmentation is a research prediction. Candidate confidence means average predicted probability within a component. It is not a diagnostic confidence score. The analysis history and reports show reference diameter, minimum lumen diameter, narrowing, and measurement location as unavailable when valid lumen measurements/calibration are absent. The current checkpoint segments stenosis lesion regions rather than vessel lumen, so the application cannot derive these measurements from its mask or candidate boxes. No clinical severity grade is assigned. Model comparison shows checkpoint metadata only unless a saved evaluation is available.

The experimental lumen geometry helper is not part of normal analysis and does not infer lumen edges from angiography. It accepts only an externally supplied expert-validated lumen contour plus validated lesion/reference regions. No such lumen annotations are currently available in the local ARCADE dataset. Therefore the application presently reports diameter and narrowing as **Unable to calculate**. Reported DICOM `PixelSpacing` is shown as metadata only; millimetre measurements require verified calibration and image-transform provenance. Do not interpret SYNTAX vessel-region widths, lesion-mask dimensions, or synthetic examples as lumen diameter or clinical stenosis.

For a newly generated lesion analysis, a user with image-preprocessing permission can optionally select **Generate Integrated Gradients attribution**. This computes an additional image over model input sensitivity against the checkpoint that created the analysis. It can take longer than ordinary inference; a progress label is shown. The attribution is saved in the existing protected analysis artifact store and appears in the case history. It is not a probability, clinical confidence, causal explanation, or validated medical interpretation. The application refuses this operation for older records that lack a saved checkpoint hash, for a changed checkpoint, or when the segmentation predicts no foreground. Vessel-region experimental runs do not support this attribution action.

Data scientists and administrators can select **Compare with ARCADE train ground truth** for an accessible lesion analysis. The backend only proceeds when the uploaded original has both the same filename and identical SHA-256 content as one image in the configured ARCADE stenosis training split; it also checks COCO dimensions, annotation category, and stored prediction-mask dimensions. It reuses the existing prediction, saves the category-26 overlap metrics and per-candidate overlap with the analysis, and provides a four-panel original/ground-truth/prediction/TP-FP-FN image. These are lesion segmentation metrics, not clinical stenosis percentages. The current case `case_008` comparison is recorded in [the comparison report](ground_truth_comparison.md) with a generated image in `reports/ground_truth_comparison/`.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| Frontend cannot reach API | Confirm backend is on port 8000 and `VITE_API_URL` matches. |
| CORS error | Keep both `localhost` and `127.0.0.1` consistent; defaults allow both Vite origins. |
| 401 after idle time | Access tokens expire; log in again. |
| DICOM rejected | Multi-frame volumes are unsupported; use a single-frame dataset. |
| Upload too large | Raise `MAX_UPLOAD_BYTES` in backend `.env`. |
| Admin APIs 403 | Public users are researchers. Run `python -m app.scripts.create_admin`. |
| Health endpoint returns 503 | The backend database readiness query failed. Confirm the configured database is reachable by the backend before retrying. |
