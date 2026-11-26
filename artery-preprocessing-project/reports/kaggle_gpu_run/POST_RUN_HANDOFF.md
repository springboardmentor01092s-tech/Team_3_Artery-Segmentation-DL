# Kaggle GPU run: local post-run handoff

The submitted kernel is `drajuakshayarao/arcade-gpu-model-sweep-2026-11-24`.
Its current version is configured for a private GPU run and the two already
uploaded private datasets. Do not upload those datasets again.

Version 1 failed before model initialization: Kaggle exposed the code dataset as
expanded `backend/...` files, while the notebook searched only for
`kaggle_project_code.zip`. The notebook now handles both layouts and copies an
expanded backend into writable Kaggle working storage. Version 2 was pushed to
the same kernel ID; it is currently queued. The remote metadata confirms GPU
enabled and both existing dataset inputs attached.

## Collect and compare after Kaggle reports COMPLETE

From the project root in PowerShell:

```powershell
$env:KAGGLE_CONFIG_DIR = Join-Path $env:USERPROFILE '.kaggle'
python .\notebooks\collect_kaggle_results.py
```

The collector downloads the existing kernel output, verifies that the archive
contains validation reports for all 200 stenosis validation images, checks the
test-split-use flag, and writes a baseline comparison to
`reports\kaggle_gpu_run\local_validation_comparison.csv` and `.json`. It does
not promote or replace a checkpoint. Extracted checkpoints remain under
`reports\kaggle_gpu_run\extracted_v2` until reviewed.

## Revalidate a candidate locally

After selecting a candidate for further review, run the project's existing
validation audit against the train/validation-only staging copy. Substitute
the candidate checkpoint path found under `extracted_v2`:

```powershell
$env:ARCADE_ROOT = (Resolve-Path '.\kaggle_upload\arcade_training_data').Path
Push-Location .\backend
.\.venv\Scripts\python.exe -m app.arcade_ml.audit_validation `
  --checkpoint '..\reports\kaggle_gpu_run\extracted_v2\<candidate>\<candidate>.pth' `
  --device cpu
Pop-Location
```

The audit uses the validation split for threshold selection and does not read
the test split unless the explicit integrity-only option is supplied (do not
supply it for model selection). Inspect Dice, IoU, precision, recall,
candidate matching at IoU 0.30/0.50, small-target metrics, false positives,
and the threshold before deciding whether the candidate is genuinely better.

Run one sample through `StenosisAnalyzer` and verify mask, overlay, heatmap,
and candidate outputs. Keep `percentage_narrowing` and severity unset because
the available polygon labels do not provide valid reference and minimum lumen
diameters.

## If considering application integration

Keep the active `best_stenosis_unet_optimized.pth` untouched. First make a
separately named, hash-verified backup; copy a candidate under a new unique
checkpoint filename; verify loading and inference through the existing backend;
then run backend tests, frontend tests, and the frontend production build. Do
not change the application's configured checkpoint until these checks pass.
No clinical validity is implied by validation-set improvements.
