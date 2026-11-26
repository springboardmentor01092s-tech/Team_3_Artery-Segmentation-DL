# API documentation

Interactive docs: `http://127.0.0.1:8000/docs`

Authenticate in Swagger with **Authorize** using a Bearer token from `POST /api/auth/login`.

## Authentication

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `PATCH /api/auth/me`
- `POST /api/auth/logout`

## Administration (administrator only)

- `GET /api/admin/users`
- `PATCH /api/admin/users/{user_id}`
- `GET /api/admin/audit-logs`

## Cases and images

- `POST /api/cases`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `PATCH /api/cases/{case_id}`
- `DELETE /api/cases/{case_id}`
- `GET /api/cases/{case_id}/access` (case owner/authorized administrator)
- `GET /api/cases/{case_id}/access-candidates` (case owner/authorized administrator)
- `POST /api/cases/{case_id}/access` (grant case access)
- `DELETE /api/cases/{case_id}/access/{grant_id}` (revoke case access)
- `POST /api/cases/{case_id}/upload`
- `GET /api/cases/{case_id}/image`
- `POST /api/cases/{case_id}/preprocess`
- `GET /api/cases/{case_id}/preprocessing-history`
- `GET /api/cases/{case_id}/processed-image/{run_id}`
- `POST /api/cases/{case_id}/analyze` (current uploaded image segmentation)
- `GET /api/cases/{case_id}/analyses` (case history)
- `GET /api/cases/{case_id}/reports/{pdf|csv|json}` (authorized case export)
- `GET /api/analyses?limit=25&offset=0&search={text}&mode={all|lesion|vessel_region_experimental}` (paginated analyses in the user's case-access scope; response includes `X-Total-Count`, `X-Page-Limit`, and `X-Page-Offset` headers)
- `GET /api/analyses/{analysis_id}`
- `GET /api/analyses/{analysis_id}/artifacts/{mask|overlay|boxes|heatmap|integrated_gradients|ground_truth_comparison}`
- `POST /api/analyses/{analysis_id}/explain` (authorized on-demand Integrated Gradients attribution for a lesion analysis)
- `POST /api/analyses/{analysis_id}/ground-truth` (data-scientist/administrator; exact-match ARCADE training comparison for an accessible lesion analysis)
- `GET /api/models/info`
- `GET /api/models/compare` (checkpoint metadata; stored metrics only)
- `GET /api/models/validation/examples` (active checkpoint's validation comparison manifest)
- `GET /api/models/validation/examples/{file_name}` (authenticated composite validation image)

## Other

- `GET /api/dashboard/stats`
- `GET /api/dataset/summary` (data scientist or administrator)
- `GET /api/health`

`GET /api/health` performs a read-only `SELECT 1` database probe. It returns HTTP 200 with `status: ok` when the database responds, and HTTP 503 with a generic `status: degraded` / `database: unavailable` check when the dependency probe fails. It does not expose connection strings or exception text. Request telemetry is written through the configured local application log and records method, route template, response status, and elapsed milliseconds; it does not record request bodies, query values, tokens, or patient data. A centralized collector still requires an operator-selected logging service and deployment configuration.

The analysis history endpoint filters records using the case visibility scope (owner, shared, assigned, or administrator visibility), supports server-side case/analysis/model search and analysis-mode filters, and paginates with `limit`/`offset`. Its body remains a JSON list for compatibility; total count and page values are response headers. The CSV case export uses actual analysis, case, image and recorded preprocessing data. Nested preprocessing/evaluation/artifact metadata is JSON-serialized within CSV cells. CSV is UTF-8 with a BOM for spreadsheet compatibility. A blank optional field means the source record has no value for that field.

## React application routes

The Vite/React client uses the API routes above through the Axios client in `frontend/src/api/client.js`. Authenticated routes are nested beneath the protected application shell in `frontend/src/App.jsx`:

| Frontend route | User workflow | API integration |
|---|---|---|
| `/dashboard` | Scoped operational statistics, recent visible cases/analyses, active model and saved validation previews | `GET /api/dashboard/stats`, `/api/cases`, `/api/analyses?limit=5`, `/api/models/info`, `/api/models/compare`, `/api/models/validation/examples` |
| `/cases`, `/cases/new`, `/cases/:caseId` | Case search/list, create and case image/analysis/history/export | `/api/cases*`, case image/preprocess/analyze/history/report endpoints |
| `/upload` | Select an accessible case, preview an image locally and upload it | `GET /api/cases`, `POST /api/cases/{case_id}/upload` |
| `/preprocess` | Select case and preprocessing parameters | `POST /api/cases/{case_id}/preprocess`, preprocessing history/image endpoints |
| `/history` | Search and filter saved analyses within the caller's case access scope | `GET /api/analyses?limit=25&offset=0&search={text}&mode={mode}` |
| `/reports` | Export one accessible case as PDF, CSV or JSON | `GET /api/cases/{case_id}/reports/{pdf|csv|json}` |
| `/models` | Read-only checkpoint metadata and saved validation comparisons | `GET /api/models/info`, `GET /api/models/compare` |
| `/dataset`, `/admin/users`, `/admin/audit` | Dataset summary and administrator management | Dataset/admin endpoints; route guards restrict roles |

The frontend route guard is for user experience; the backend remains the authority for authentication, role checks, case visibility, upload permissions and protected artifacts. A route/page test does not replace a live browser-to-API check.

Analysis responses contain mask-component candidates, predicted-probability values, model checkpoint SHA-256 provenance, and protected visualization URLs. `POST /api/analyses/{id}/explain` performs an optional 16-step Integrated Gradients calculation against the same checkpoint hash and adds an `integrated_gradients` artifact plus method metadata to the existing analysis record. This operation requires the caller to have case access and image-preprocessing permission. It returns 409 for legacy records without checkpoint identity, changed/missing active checkpoints, or unsupported analysis modes; 422 when there is no predicted foreground or valid attribution; and 503 for inference/runtime errors. Attribution is relative model input sensitivity, not clinical confidence, probability, diagnosis, or validated evidence. The probability heatmap and segmentation overlay remain separate visualizations and are not Grad-CAM.

Analysis responses also include `diameter_measurement` with status, reference vessel diameter in mm, minimum lumen diameter in mm, measurement location, percentage, and an explanatory reason. With the current lesion-region checkpoint these fields are unavailable/null: the checkpoint does not segment lumen boundaries, and pixel spacing alone is insufficient. Reports retain the same fields. JSON includes any saved explanation metadata; CSV includes method and integration steps; PDF notes the attribution and its limits. The guarded arithmetic helper accepts only externally validated millimetre measurements, calibrated images, validated lumen/reference geometry, perpendicular cross-sections, and in-image locations; it is not called with lesion masks or candidate boxes.

The measurement payload also reserves `reference_vessel_diameter_px`, `minimum_lumen_diameter_px`, reference/minimum image coordinates, `quality`, and quality notes. These remain unavailable in ordinary case analyses because this application has no expert lumen mask or validated lesion/reference ROIs. There is currently no lumen-segmentation or lumen-measurement API endpoint. `backend/app/arcade_ml/lumen_measurement.py` is an opt-in geometry utility for externally supplied expert-validated 2D lumen masks and ROIs; it is not wired to lesion or SYNTAX predictions. Its synthetic unit tests verify geometry behavior only and are not image validation. A caller can obtain pixel widths from such a mask; millimetres and percentage additionally require explicit trusted DICOM plane calibration and transform verification. Routine analysis always sets those verification flags false and does not consume reported `PixelSpacing` as measurement calibration.

`POST /api/analyses/{analysis_id}/ground-truth` matches the analysis source against `stenosis/train/annotations/train.json` by original filename **and exact image file SHA-256**, then checks COCO and prediction-mask dimensions before computing category-26 lesion-pixel Dice/IoU/precision/recall/TP/FP/FN. It uses the persisted prediction mask and does not rerun or retrain the model. It stores identity, metrics, per-component overlap, and a four-panel visualization under the existing analysis record/artifact store. Access requires case visibility and `dataset:inspect` permission (data scientist or administrator). It returns 409 for mismatched dimensions, missing prediction artifacts, unmatched candidates, or unsupported modes; 503 if the configured train annotation source is unavailable. Metrics compare lesion labels only and are not clinical narrowing or lumen measures. The JSON export includes the full comparison; CSV/PDF include aggregate metrics and candidate overlaps.

Unauthorized requests return **401**. Forbidden role or ownership failures return **403**. Validation errors return **422**. Oversized uploads return **413** when the size limit is hit during streaming.
