# ARCADE Ground-Truth Audit and Model Validation

Run date: 2026-11-24. Source data at `ARCADE_ROOT` was read-only. The report scripts, predictions, plots, and checkpoints are saved under this application.

## Dataset audit

The stenosis target is COCO category ID **26** (`stenosis`). Its polygons were rasterized against their own COCO image records by `image_id`; images and masks were compared in the same 512×512 pixel coordinates. All image files are 512×512 and match the dimensions recorded in the annotation JSON. Every split had zero missing images, orphan image files, unreadable images, dimension mismatches, missing polygons, degenerate polygons, duplicate COCO IDs, orphan annotation references, or invalid boxes.

| Task | Split | Images | Annotation objects | Positive target masks | Empty target masks | Foreground pixels (min / median / max) |
|---|---:|---:|---:|---:|---:|---:|
| Stenosis, category 26 | Train | 1,000 | 1,625 | 997 | 3 | 0 / 1,669.5 / 9,424 |
| Stenosis, category 26 | Validation | 200 | 406 | 200 | 0 | 233 / 2,029.5 / 9,885 |
| Stenosis, category 26 | Test | 300 | 386 | 300 | 0 | 323 / 2,232.5 / 8,979 |
| Syntax, all annotated categories | Train | 1,000 | 4,976 | 1,000 | 0 | 1,187 / 8,294.5 / 22,914 |
| Syntax, all annotated categories | Validation | 200 | 1,168 | 200 | 0 | 3,238 / 8,677.5 / 22,137 |
| Syntax, all annotated categories | Test | 300 | 1,672 | 300 | 0 | 1,894 / 8,734.5 / 22,006 |

All annotations use polygon-list segmentations. Stenosis foreground occupies about **0.79%** of train pixels, showing strong class imbalance. Exact duplicate audit found three duplicate pairs within stenosis train, one cross-split stenosis duplicate (`train/218.png` = `val/58.png`), and five duplicate pairs within syntax train. Current training excludes within-train duplicates and training copies of validation images with matching content hashes. The existing checkpoint’s training exposure to the cross-split duplicate cannot be established from its metadata.

The test rows and duplicate information above are from a historical integrity audit. Earlier audit commands read test images/annotations for file/hash/mask integrity, but generated no test predictions or model-selection metrics. Thus the test split was not strictly untouched. From this handoff onward, the training loader and default validation audit read train/validation only; the Kaggle sweep does not open test files.

No category names or fields provide lumen boundaries, calibrated vessel diameters, or reference/minimum lumen measurements. The available source images are PNG, and the dataset JSON has no physical pixel spacing. Thus anatomical percentage narrowing and clinical severity grading are unsupported. Stenosis lesion polygons and bounding boxes are not lumen-diameter substitutes.

## Existing checkpoint: full validation evaluation

Checkpoint: `backend/checkpoints/best_stenosis_unet_optimized.pth` (architecture `legacy_unet`, input 256×256, epoch 47). The checkpoint’s stored metadata states Dice ≈0.4336 and IoU ≈0.2980; it has no per-epoch history. Those stored figures are not treated as fresh evaluation results.

The evaluation used all 200 validation images, generated predictions from the matching image, resized predictions back to 512×512, rasterized the corresponding category-26 polygons at 512×512, and applied the same 20-pixel component filter. Threshold selection maximized per-image macro Dice on validation only. The held-out test split was not used for tuning or model selection.

| Threshold | Validation macro Dice | Global pixel Dice | Macro IoU |
|---:|---:|---:|---:|
| 0.25 | 0.42383 | 0.44363 | 0.28843 |
| 0.35 | 0.42860 | 0.45000 | 0.29298 |
| 0.45 | 0.43074 | 0.45357 | 0.29517 |
| 0.50 | 0.43128 | 0.45467 | 0.29576 |
| **0.55 selected** | **0.43169** | **0.45558** | **0.29631** |
| 0.65 | 0.43109 | 0.45616 | 0.29604 |
| 0.75 | 0.42792 | 0.45386 | 0.29347 |

At the selected threshold the global pixel confusion counts were TP 246,158; FP 391,963; FN 196,351; TN 51,594,328. Global precision 0.38575, recall/sensitivity 0.55628, F1 0.45558, and specificity 0.99246. Per-image macro precision 0.42258, recall 0.56321, specificity 0.99246. Empty-ground-truth/empty-prediction Dice and IoU use additive epsilon smoothing and score 1; the validation split contains no empty target masks. The 0.55 threshold is applied through a separate JSON sidecar; the `.pth` checkpoint is unchanged. Its macro Dice gain over 0.50 is only 0.00040, so this is a marginal threshold adjustment, not a model improvement.

Candidate matching uses predicted connected-component boxes against category-26 COCO boxes, with minimum component area 20 pixels and one-to-one greedy matching (predictions ordered by mean predicted probability). At IoU ≥0.30: **108 TP, 497 FP, 298 FN**, precision 0.17851, recall 0.26601, F1 0.21365. At IoU ≥0.50: **58 TP, 547 FP, 348 FN**, precision 0.09587, recall 0.14286, F1 0.11474. There were 605 predicted components (area min/median/max 20/550/6,979 pixels). This is weak localization performance. Component mean predicted probability is not clinical confidence.

Positive validation images are grouped by category-26 mask-area quartiles. Small (≤Q25, 50 images): macro Dice 0.29286, IoU 0.19075, recall 0.52332; candidate IoU-0.30 counts 13/124/49 TP/FP/FN. Medium (Q25–Q75, 100 images): Dice 0.46856, IoU 0.32187, recall 0.60804. Large (≥Q75, 50 images): Dice 0.49677, IoU 0.35074, recall 0.51344. Validation contains no empty target images, so empty-mask validation performance cannot be measured.

Minimum-component area was compared at selected threshold 0.55. Areas 0/20/50/100 pixels gave macro Dice 0.43166/0.43169/0.43186/0.43267 and candidate IoU-0.30 counts 108/542/298, 108/497/298, 108/455/298, and 108/413/298. Candidate TP/FN were unchanged in this validation set while FP fell; small-target Dice was 0.29278/0.29286/0.29326/0.29477. This is a modest validation-only trade-off, not a clinically validated filter. The deployed filter remains 20 pixels to avoid selecting a post-process from the same validation set without independent confirmation.

## Training experiment: ResUNet

Hardware was CPU-only (`torch 2.14.1+cpu`, no CUDA). One reproducible eight-epoch experiment trained ResUNet base width 16 at 256×256 with AdamW, BCE+Dice loss, positive weight 5, flips/rotations, seed `20261124`, and validation-based best-checkpoint selection. It used 996 training images after excluding train duplicates and the known train/validation exact duplicate. Validation data were not fed to the optimizer; no test predictions or metrics were computed. The current training loader reads validation hashes only to prevent exact duplicate leakage. The original checkpoint was backed up before training and neither it nor the active model was overwritten.

| Epoch | Train loss | Train macro Dice | Train macro IoU | Val loss | Val macro Dice | Val macro IoU |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.2909 | 0.0971 | 0.0570 | 1.1445 | 0.1976 | 0.1158 |
| 2 | 1.0648 | 0.2141 | 0.1285 | 1.0739 | 0.1291 | 0.0757 |
| 3 | 0.9470 | 0.2447 | 0.1501 | 0.9527 | 0.2403 | 0.1496 |
| 4 | 0.8778 | 0.2686 | 0.1680 | 0.8844 | 0.2765 | 0.1761 |
| 5 | 0.8467 | 0.2845 | 0.1797 | 0.8665 | 0.2825 | 0.1817 |
| 6 | 0.8225 | 0.3012 | 0.1929 | 0.8071 | 0.3210 | 0.2061 |
| 7 | 0.8010 | 0.3178 | 0.2054 | 0.8256 | 0.3031 | 0.1978 |
| **8 (best)** | **0.7915** | **0.3230** | **0.2105** | **0.7783** | **0.3447** | **0.2264** |

The best experiment checkpoint is `backend/checkpoints/resunet16_stenosis_experiment.pth`, not active. Under the same full-resolution validation evaluator, its selected threshold was 0.35, macro Dice 0.34666, global Dice 0.35409, macro IoU 0.22766, candidate TP/FP/FN 55/567/351, candidate precision 0.08842, recall 0.13547. Compared with the active legacy model it is worse by 0.08503 macro Dice and 0.06865 macro IoU. It was not promoted.

The primary observed bottleneck is not simply architecture: model predictions include many non-target vessel regions while the annotations mark stenosis polygons; combined with <1% foreground, this creates false positives and limited candidate recall. The existing checkpoint and eight-epoch ResUNet were compared on the same full-resolution evaluator; ResUNet was materially worse. A 384×384 Attention U-Net base-8 run saved a best epoch-5 checkpoint before interruption (5 of 6 requested epochs); it is a partial experiment, not a completed training run. Its full-resolution validation was substantially worse than baseline. Training time was not persisted when the run was interrupted. The machine is CPU-only, so the broader pretrained-encoder sweep was prepared for Kaggle GPU rather than run locally.

The experiment CLI supports U-Net/Attention U-Net/ResUNet and SMP U-Net/U-Net++/DeepLabV3+ architectures, BCE+Dice/Focal/Tversky/Focal-Tversky losses, Adam/AdamW, plateau/cosine scheduling, AMP, gradient accumulation, conservative paired augmentation, and optional positive-image weighted sampling. ImageNet normalization is recorded and applied identically in training and app inference. The active checkpoint retains its original `/255` normalization. A secret-free bundle builder and Kaggle GPU notebook were added; pretrained SMP experiments remain unrun pending Kaggle execution.

## Visual validation examples

Each image shows original, category-26 ground truth, predicted mask with candidate boxes, and probability heatmap. It also prints threshold, Dice, IoU, precision, recall, and candidate TP/FP/FN. Baseline, ResUNet, and partial Attention U-Net reports each contain 50 distinct validation examples chosen from measured outcomes, including low/high Dice, false positives/negatives, and target-size ranks. All 200 validation images are evaluated; 50 are shown per model.

- Best Dice: [126.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/best_dice_126.png)
- Worst Dice / missed region: [178.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/worst_dice_178.png)
- Largest pixel false-positive count: [41.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/false_positive_41.png)
- Largest pixel false-negative count: [112.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/false_negative_112.png)
- Smallest positive validation target (233 pixels): [173.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/small_ground_truth_173.png)
- Largest positive validation target: [142.png](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/large_ground_truth_142.png)
- Additional examples: [`validation_comparisons_best_stenosis_unet_optimized`](../reports/model_validation/validation_comparisons_best_stenosis_unet_optimized/)
- ResUNet: [`validation_comparisons_resunet16_stenosis_experiment`](../reports/model_validation/validation_comparisons_resunet16_stenosis_experiment/)
- Attention U-Net: [`validation_comparisons_attention_unet8_384_stenosis_experiment`](../reports/model_validation/validation_comparisons_attention_unet8_384_stenosis_experiment/)

There are no empty-ground-truth validation images to visualize. Heatmaps represent predicted segmentation probability and are not Grad-CAM.

## Generated artifacts

- Historical full integrity audit (includes test file integrity reads): [`dataset_audit.json`](../reports/model_validation/dataset_audit.json)
- Routine train/validation-only audit: [`dataset_audit_train_val.json`](../reports/model_validation/dataset_audit_train_val.json)
- Legacy per-image results: [`validation_per_image.csv`](../reports/model_validation/validation_per_image.csv)
- Legacy full metrics: [`validation_metrics_best_stenosis_unet_optimized.json`](../reports/model_validation/validation_metrics_best_stenosis_unet_optimized.json)
- ResUNet per-image results: [`validation_per_image_resunet16_stenosis_experiment.csv`](../reports/model_validation/validation_per_image_resunet16_stenosis_experiment.csv)
- ResUNet full metrics: [`validation_metrics_resunet16_stenosis_experiment.json`](../reports/model_validation/validation_metrics_resunet16_stenosis_experiment.json)
- Training history and plots: [`training_history.json`](../reports/model_validation/resunet16_stenosis_experiment/training_history.json), [loss](../reports/model_validation/resunet16_stenosis_experiment/loss_curve.png), [Dice](../reports/model_validation/resunet16_stenosis_experiment/dice_curve.png), [IoU](../reports/model_validation/resunet16_stenosis_experiment/iou_curve.png)
- Attention U-Net checkpoint/config/history: [checkpoint](../backend/checkpoints/attention_unet8_384_stenosis_experiment.pth), [config](../reports/model_validation/attention_unet8_384_stenosis_experiment/experiment_config.json), [history](../reports/model_validation/attention_unet8_384_stenosis_experiment/training_history.json)
- Unified comparison: [CSV](../reports/model_validation/experiment_comparison.csv), [chart](../reports/model_validation/experiment_comparison.png)
- Kaggle workflow: [notebook](../notebooks/arcade_gpu_model_sweep.ipynb), [safe bundle builder](../notebooks/build_kaggle_bundle.py)
- Original checkpoint backup: `backend/checkpoints/best_stenosis_unet_optimized.pth.pre-improvement.bak`

No test-set prediction metrics are reported. No image-derived stenosis narrowing or severity is computed. A validated-input-only formula helper is covered by unit tests but has no measurement source in this application.

## Experiment comparison and selection

| Model | Training status | Full-resolution validation macro Dice | Macro IoU | Global Dice | Candidate TP/FP/FN at IoU 0.30 | Decision |
|---|---|---:|---:|---:|---:|---|
| Existing legacy U-Net checkpoint, 256 input, threshold 0.55 | Existing checkpoint; full 200-image validation reproduced | 0.43169 | 0.29631 | 0.45558 | 108/497/298 | Retain as active model |
| ResUNet, base 16, 256 input | 8 completed epochs; 996 deduplicated train images | 0.34666 | 0.22766 | 0.35409 | 55/567/351 | Do not promote |
| Attention U-Net, base 8, 384 input | 5/6 epochs; interrupted, best checkpoint retained | 0.27833 | 0.17646 | 0.29571 | 27/536/379 | Do not promote |

At candidate IoU 0.50, TP/FP/FN were 58/547/348 (F1 0.11474) for legacy U-Net, 17/605/389 (F1 0.03307) for ResUNet, and 8/555/398 (F1 0.01651) for Attention U-Net. Small/medium/large macro Dice were 0.29286/0.46856/0.49677, 0.18343/0.37383/0.45555, and 0.15478/0.30380/0.35092, respectively. The active baseline is better in all reported groups among these measured models.

The active checkpoint is best among the measured runs, but candidate-localization quality remains weak. CPU inference was measured on all validation images including image I/O/preprocessing: about 0.131 seconds/image for the active model, 0.085 for ResUNet, and 0.071 for Attention U-Net. Parameter counts/checkpoint bytes were 1,925,601/7,716,521; 2,031,137/8,204,915; and 492,425/2,050,667, respectively. These timings are machine-specific; GPU memory was unavailable. Training histories include the best training/validation-size Dice and IoU for both experiments. The old ResUNet run and interrupted Attention run did not persist exact total training time. Hardware at inspection: 12 logical CPUs, 15.65 GiB RAM with 4.68 GiB available, PyTorch 2.14.1 CPU-only, and 288.8 GiB free on the project volume. The ARCADE image payload is approximately 0.42 GiB.

Image-derived percentage narrowing remains unavailable: required lumen boundaries, reference/minimum lumen diameters, physical pixel calibration, and anatomically validated reference segments are absent. A guarded arithmetic helper exists for externally validated millimetre measurements and is not called by lesion-mask inference.

## Reproduction command

From `backend` in PowerShell, a completed ResUNet run can be reproduced with:

```powershell
python -m app.arcade_ml.train_experiment --architecture resunet --loss bce_dice --optimizer adamw --epochs 8 --patience 4 --batch-size 4 --image-size 256 --base-channels 16 --learning-rate 0.0005 --pos-weight 5 --seed 20261124 --threads 6 --output checkpoints\resunet16_stenosis_experiment.pth
python -m app.arcade_ml.audit_validation --checkpoint checkpoints\resunet16_stenosis_experiment.pth --device cpu
```

The output checkpoint path auto-suffixes if it already exists. New training/audit workflows access train and validation only. The historical test integrity reads described above mean it should not be described as a strictly untouched holdout. The active production checkpoint remains `backend/checkpoints/best_stenosis_unet_optimized.pth` and was not replaced.

## Kaggle GPU handoff

Private inputs are already present as `drajuakshayarao/arcade-train-val-private-nov2026` and `drajuakshayarao/arcade-project-code-private-nov2026`. The existing kernel is `drajuakshayarao/arcade-gpu-model-sweep-2026-11-24`; Version 1 failed before model initialization because Kaggle expanded the code ZIP into `backend/...` files and the notebook searched only for a ZIP. The log is retained at [`reports/kaggle_gpu_run/arcade-gpu-model-sweep-2026-11-24.log`](../reports/kaggle_gpu_run/arcade-gpu-model-sweep-2026-11-24.log). Notebook code discovery now accepts both an archive and an expanded backend tree, copies expanded code to writable Kaggle working storage, and checks CUDA before training. Version 2 was pushed to the same kernel ID. Its last recorded status was `QUEUED`; no Version 2 training, GPU identity, or metrics are available. Remote metadata confirms GPU enabled and both private dataset inputs attached. No queue position or accelerator capacity reason was returned.

The notebook plans pretrained ResNet34/EfficientNet-B0 U-Net, U-Net++, DeepLabV3+, Attention U-Net, 256/384/512 resolutions, and a focal-Tversky ablation. It evaluates validation only and does not open test files. After Kaggle reports successful completion, use [`notebooks/collect_kaggle_results.py`](../notebooks/collect_kaggle_results.py) and follow the [local post-run handoff](../reports/kaggle_gpu_run/POST_RUN_HANDOFF.md). No Kaggle model has been trained or promoted as of this report update.

SMP checkpoints store encoder and ImageNet-normalization metadata; the application loader now supports them when the optional `backend\\requirements-ml.txt` dependency is installed. If a Kaggle model beats baseline meaningfully, copy its checkpoint and threshold sidecar to unique names, then verify local inference/API/export paths before setting `MODEL_CHECKPOINT`. No model has been promoted.
