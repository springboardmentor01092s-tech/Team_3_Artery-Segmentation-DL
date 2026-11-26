# Experimental ARCADE SYNTAX vessel-region segmentation

## What the annotations mean

The `syntax/train` and `syntax/val` COCO files contain polygon annotations for coronary artery segments (categories 1–25). The separate `stenosis` task uses category 26 polygons for lesion regions. SYNTAX annotations are distinct from lesion polygons, but they do not establish a complete lumen-wall contour: coverage is segment-specific, some visible branches are unlabeled, and the PNG/COCO records contain no lumen calipers, reference segment, or physical pixel spacing. This model predicts the union of annotated coronary segment regions, not a clinically complete lumen boundary.

The official ARCADE task describes coronary artery segmentation and stenosis detection as distinct tasks ([task description](https://arcade.grand-challenge.org/tasks/)); the dataset paper likewise describes separate annotation tasks ([Scientific Data paper](https://doi.org/10.1038/s41597-023-02871-z)). This project keeps those targets separate.

## Experimental pipeline

`backend/app/arcade_ml/train_experiment.py --task syntax` trains on SYNTAX train annotations and validates on SYNTAX val. It writes task-tagged checkpoints under `backend/checkpoints/`; when a target exists, it chooses a suffixed filename rather than overwriting it. `backend/app/arcade_ml/evaluate_syntax_vessels.py` evaluates only `syntax/val`, selects a threshold using validation macro Dice, writes JSON and per-image CSV metrics, and saves worst/median/best validation overlays. These commands never read test. Validation-selected scores are exploratory, not an independent test estimate.

The target mask unions all annotated polygons in an image. It does not infer that unlabeled pixels contain no artery and does not convert lesion regions into lumen labels. This model remains separate from active lesion inference and is not integrated into the clinical analysis workflow.

## Reproduction

Run from `backend` using the project virtual environment (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m app.arcade_ml.train_experiment --task syntax --architecture unet --base-channels 8 --epochs 5 --batch-size 8 --image-size 256 --pos-weight 2 --threads 6 --seed 20261124 --output checkpoints\syntax_unet8_experiment.pth
.\.venv\Scripts\python.exe -m app.arcade_ml.evaluate_syntax_vessels --checkpoint checkpoints\syntax_unet8_experiment.pth
.\.venv\Scripts\python.exe -m app.arcade_ml.train_experiment --task syntax --architecture resunet --base-channels 8 --epochs 5 --batch-size 8 --image-size 256 --pos-weight 2 --threads 6 --seed 20261124 --output checkpoints\syntax_resunet8_full5e_20261125.pth
.\.venv\Scripts\python.exe -m app.arcade_ml.evaluate_syntax_vessels --checkpoint checkpoints\syntax_resunet8_full5e_20261125.pth
```

## Results

Both models were trained from scratch on CPU with 256×256 inputs, 8 base channels, batch size 8, 5 epochs, BCE+Dice loss, AdamW at 0.0005, conservative augmentation, 6 CPU threads, and seed `20261124`. The same 995 unique training images (five within-train duplicate filenames excluded) and 200 validation images were used. No test data was accessed.

| Model | Best epoch | Train time | Selected validation threshold | Macro Dice | Macro IoU | Global Dice | Precision | Recall | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| U-Net | 4 | 412.84 s | 0.75 | 0.74255 | 0.59695 | 0.74530 | 0.73356 | 0.75742 | 0.98977 |
| ResUNet | 5 | 664.87 s | 0.65 | 0.73742 | 0.59165 | 0.74287 | 0.72829 | 0.75805 | 0.98949 |

U-Net was slightly higher on validation macro Dice/IoU. Both thresholds were selected on the same validation set used for scoring, so this difference is exploratory, not an independent comparison. The comparison is between segment-polygon models, not against the active lesion model, and says nothing about lumen-boundary or stenosis performance. Full per-image metrics and best/median/worst overlays are under `reports/vessel_segmentation/`; training history/config/curves are under `reports/model_validation/syntax_*`.

## Diameter and narrowing are unavailable

No automatic diameter is derived from these outputs. There is no validated complete lumen-boundary ground truth, same-vessel reference segment annotation, or image calibration associated with ARCADE PNG/COCO data. A source DICOM PixelSpacing value, where available, cannot by itself recover spacing after export/cropping/transforms or identify the clinically appropriate reference segment. The guarded narrowing formula helper is not called by this experimental pipeline. It must continue to return “Unable to calculate” unless trusted minimum and reference lumen diameters in the same calibrated units are supplied. No percentage, severity grade, or clinical claim is inferred from polygon width, area, or model confidence.

The active lesion U-Net, inference interface, database, uploads, processed files, source dataset, staged training bundle, and Kaggle configuration are preserved. Neither experimental checkpoint is promoted.

## Other supplied annotation formats audited

The SYNTAX split folders also contain binary PNG masks (1,000 train, 200 validation, 300 test). A sample is 512×512, 8-bit grayscale with foreground value 255 and background 0. On the 200 validation images, the supplied binary masks and the COCO polygon union have mean pixel IoU 0.911 (none are byte/pixel-identical); the experiment and its reported metrics use COCO polygons, as implemented in the loader. This confirms an artery-segment foreground target, but not lumen-caliper annotations or physical calibration. Test COCO schema was inspected only for available fields; no test predictions or metrics were computed, and test labels were not used for training, threshold selection, or model selection.

The train/validation/test COCO schema contains polygons, bounding boxes, area, category IDs, and an `occluded` attribute. Image metadata exposes width/height and file name; neither annotation records nor PNG masks contain a pixel-spacing or diameter/reference measurement field. The category protocol is segment labeling under SYNTAX, not a separate annotated inner/outer vessel-wall or reference-segment measurement task ([official challenge task description](https://arcade.grand-challenge.org/tasks/), [ARCADE dataset paper](https://doi.org/10.1038/s41597-023-02871-z)).


## Application mode and pixel-width method

The case page keeps lesion analysis selected by default and offers `Experimental vessel-region` as an explicit optional mode. The API endpoint remains `/api/cases/{case_id}/analyze`; the optional query is `mode=vessel_region_experimental`. It uses only `backend/checkpoints/syntax_unet8_experiment.pth` and requires that checkpoint's validation-only JSON report for its probability threshold. The model output is filtered into connected components; a morphological skeleton provides centerline samples, local PCA estimates the vessel axis, and image-mask intersections are measured along the perpendicular normal. Branch-ambiguous, too-small, too-short, and image-edge-clipped sections are omitted. Results include pixel width, pixel coordinates, local orientation, and a qualitative geometry check. These samples are exploratory widths of a predicted segment-region mask, not anatomical lumen measurements or lesion candidates.

The analysis history stores `analysis_mode`, target semantics, pixel widths and quality notes in the existing result JSON, with no schema migration. The mode returns protected mask/overlay/centerline/cross-section/heatmap artifacts, and JSON/CSV/PDF exports include the mode and width fields. Width estimates are never sent to `calculate_validated_stenosis_percentage`; reference and minimum lumen diameters and narrowing percentage remain “Unable to calculate”. The API uses the same case permission check and protected-artifact route as lesion analysis.

A real validation-image smoke check on `syntax/val/images/1.png` (512×512) yielded 11 connected components, 24 sampled widths, and a smallest sampled estimate of 3.5 px at the selected 0.75 threshold. This demonstrates the pixel routine runs on an image; it does not establish accuracy or clinical relevance.

Width quality parameters: the current estimator omits connected components smaller than 30 pixels, skeletons shorter than 7 pixels, local PCA neighborhoods with fewer than 5 skeleton points or linearity ratio below 1.6, and cross-sections outside 1.5–60 pixels or clipped by the image edge. It selects at most 24 spatially separated samples, prioritizing smaller widths. This is a code-quality filter only; it is not a clinical confidence score and cannot validate a stenotic narrowing.
