# Lumen diameter and stenosis percentage: completion audit

## Acceptance result

| Requirement | Status | Reason |
|---|---|---|
| Actual lumen diameter in millimetres | **Blocked** | There is no validated lumen-boundary segmentation/contour for a lesion and matched reference segment in the local ARCADE data. Existing vessel-region widths are not lumen diameters. Local uploaded records are PNG and have no physical spacing. |
| Automatic stenosis percentage from images | **Blocked** | Neither required diameter is produced with validated lumen boundaries; there is also no verified physical calibration or validated lesion/reference cross-section pair. The formula helper is guarded and the API correctly returns “Unable to calculate.” |

No code was added that infers lumen boundaries from lesion masks, SYNTAX masks, image intensity, or candidate boxes. There was no suitable ground truth against which such inferred boundaries could be validated. The active lesion model and experimental SYNTAX model were left unchanged.

## Existing measurement path

- `backend/app/arcade_ml/inference.py`: the active U-Net predicts category-26 stenosis lesion regions. Its `DIAMETER_MEASUREMENT_UNAVAILABLE` payload explicitly says the output is not a lumen boundary and leaves all diameter/percentage fields null.
- `backend/app/arcade_ml/vessel_width.py`: extracts centerlines and perpendicular widths from the binary SYNTAX segment-region prediction. It labels results `estimated_vessel_region_width_not_lumen_diameter` and reports pixels only. It does not estimate minimum lumen or a lesion-free reference diameter.
- `backend/app/arcade_ml/diameter_measurement.py`: accepts externally supplied millimetre diameters only if units, calibration, lumen boundaries, reference location, perpendicular sections, and image locations are all attested. It performs formula validation only; it does not segment or measure an image.
- `backend/app/api/analysis.py` and `frontend/src/pages/CaseDetailPage.jsx`: the API persists and returns the null guarded measurement. The UI displays “Unable to calculate” with its reason. The experimental mode separately shows pixel vessel-region widths and never calls the stenosis formula.

## Calibration findings

`backend/app/preprocessing/pipeline.py` reads DICOM `PixelSpacing` into `LoadedImage.metadata`. `backend/app/services/image_service.py` serializes that metadata into the existing `UploadedImage.metadata_json` on upload. In the analysis endpoint, the original DICOM is reloaded and its pixels are used, but `loaded.metadata` is currently discarded. No pixel-spacing validation or mm conversion exists in the analysis path.

A read-only inventory of the current database found five uploaded-image records, all PNG, with no `pixel_spacing` metadata. The checked ARCADE image collections are PNG/COCO data and their annotations do not carry spacing or diameter/reference fields. Thus no current application image supports an mm result. Even when a future DICOM has `PixelSpacing`, it must be validated as finite, positive, correctly ordered row/column spacing and shown to be valid for the angiographic image plane after any transforms; pixel spacing alone cannot supply the missing lumen contours or reference protocol.

## Ground-truth and external-data assessment

ARCADE stenosis labels are lesion polygons. ARCADE SYNTAX labels and binary masks label named artery regions, with some visible branches outside the annotation protocol. Neither target specifies the inner contrast-filled lumen boundary or a matched minimum-lumen/reference measurement. These task labels are therefore not enough for stenosis QCA ground truth ([official ARCADE task definition](https://arcade.grand-challenge.org/tasks/), [ARCADE dataset paper](https://doi.org/10.1038/s41597-023-02871-z)).

An invasive-angiography segmentation study reports expert-confirmed artery contours and image pixel sizes for 294 angiograms, which could be a candidate source for vessel-contour research if its data and label semantics can be obtained. The inspected publication does not establish that this project can access those images or that they include independent, lesion-level QCA reference diameter and MLD ground truth ([study record](https://pubmed.ncbi.nlm.nih.gov/35875389/)). It is not used here.

ImageCAS-X/Coronary Atlas provides lumen voxel labels and centerlines for coronary CT angiography, but CTCA is a different modality from the app’s invasive X-ray angiography and does not validate 2D projection QCA measurements ([dataset/benchmark](https://kitbransby.github.io/ImageCAS-X/), [dataset paper](https://www.nature.com/articles/s41597-023-02016-2)). A published external CathAI QCA dataset describes core-lab reference diameter and MLD data but is not publicly available in the inspected report ([study/data availability](https://pmc.ncbi.nlm.nih.gov/articles/PMC10421915/)). These sources show what suitable validation may require; none has been imported or used in this project.

A validated QCA reference protocol is also required. The DICOM QCA reference method reconstructs the reference diameter from vessel portions outside the lesion rather than substituting an arbitrary nearby width ([DICOM PS3.17 QCA reference method](https://dicom.nema.org/medical/Dicom/2023e/output/html/part17.html)). Clinical use would additionally require cardiology/core-lab adjudication and external validation against the selected reference standard.

## Requirements to unblock

1. Provide access to real invasive coronary angiography cases in original DICOM form (or an equivalent calibrated format), with validated image-plane calibration and transform provenance.
2. Obtain expert-adjudicated inner lumen contours or QCA MLD and reference diameter, plus lesion and reference cross-section coordinates, tied to the same image/view.
3. Define and validate the reference-segment/QCA protocol, handling foreshortening, overlap, projection angle, and image quality.
4. Train/validate a separate lumen-boundary method on suitable training cases and evaluate on held-out patient-level cases against the reference standard. Do not use ARCADE lesion/SYNTAX masks as substitute lumen labels.
5. Only after measurement validation, pass compatible calibrated measurements through the existing guarded formula and report uncertainty/quality separately from clinical probability.

Until these requirements are met, the two requested clinical measurement features remain blocked. Pixel-only SYNTAX region widths may be displayed as experimental geometry, but must not be renamed or converted into lumen diameters or stenosis percentages.

## Geometry utility continuation (2026-11-25)

`backend/app/arcade_ml/lumen_measurement.py` implements an isolated geometry path for **externally supplied expert-validated inner-lumen masks**. The caller must also provide expert-validated lesion and reference ROIs on the same connected lumen component. The method estimates a centerline from the binary mask, a local direction by PCA of nearby skeleton points, samples the mask along the perpendicular normal, chooses the narrowest section in the validated lesion ROI, and uses the median of at least three valid reference sections. It returns pixel diameters and locations; `draw_lumen_measurement` renders the supplied contour, centerline, and calipers.

Millimetre conversion additionally requires DICOM PixelSpacing marked reported-valid, finite positive row/column values, and explicit calibration and transform verification. Conversion respects the cross-section normal and anisotropic spacing. Normal API analysis never sets these attestations; the utility is not wired to inference, and no current case supplies its required contour/ROI inputs. The helper cannot independently prove caller-provided validation flags, so any future integration must restrict input to a trusted expert annotation workflow. Geometric quality is not clinical confidence. Synthetic-mask tests verify implementation behavior only; there is no real-image validation and acceptance remains blocked.

No database columns or automatic backfills were added. Current case UI and JSON/CSV/PDF outputs continue to report missing diameters and stenosis as unavailable. Required external data remain original calibrated invasive angiography, expert-adjudicated lumen contours and lesion/reference coordinates (or core-lab QCA MLD/reference values), a defined reference protocol, and independent patient-level validation.
