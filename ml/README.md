# Baseline syntax segmentation training

The baseline trainer uses the existing `UNet(in_channels=1, out_channels=1)` and ARCADE's prepared `syntax` task. It reads `train` for optimizer updates and `val` for epoch metrics and best-checkpoint selection. It never opens or uses the `test` split during training or model selection.

## Dataset layout and assumptions

The default roots are `C:\Users\namde\Downloads\arcade\arcade` and `C:\Users\namde\Downloads\arcade\arcade_prepared_masks`. The loader expects:

```text
<dataset-root>/syntax/<split>/images/*.png
<mask-root>/syntax/<split>/masks/*.png
```

Files are paired by case-insensitive filename stem. Images are converted to 8-bit grayscale, resized to 256×256 with Lanczos, and scaled to float32 `[0,1]`. Category-ID masks are resized with nearest-neighbor interpolation and converted in memory to binary float32 masks (`0` remains background; any nonzero category becomes foreground). Source images and masks are never changed. The input intensity scaling is a baseline assumption; it must be reviewed against the training protocol before clinical or research conclusions are drawn.

## Train

From the project root:

```powershell
python -m ml.train_baseline --epochs 30 --batch-size 2
```

To set roots and outputs explicitly:

```powershell
python -m ml.train_baseline `
  --dataset-root "C:\Users\namde\Downloads\arcade\arcade" `
  --mask-root "C:\Users\namde\Downloads\arcade\arcade_prepared_masks" `
  --epochs 30 --batch-size 2 --output-dir ml
```

The script selects CUDA when available and otherwise uses CPU. On CPU it caps PyTorch compute threads and inter-op threads at 4 by default (`--cpu-threads` overrides this); the previous runtime default was 14 threads in each pool on the inspected machine. It fixes Python, NumPy, and PyTorch seeds, disables cuDNN benchmarking, uses zero data-loader workers, Adam, and equal-weight BCE-with-logits plus soft Dice loss. Every epoch validates on `val`; the best checkpoint is `ml/checkpoints/best_unet.pt` and the report is `ml/reports/baseline_training_report.json` by default. The report includes per-epoch train loss, validation loss, validation Dice, CPU thread settings, and explicitly records that the test split was not used. Dice is a segmentation metric on this dataset split, not clinical validation.

The default resolution and batch size remain 256×256 and 2. `--image-size` accepts square values divisible by 16, as required by the existing U-Net's four downsampling stages. Lower resolutions reduce activation memory and CPU compute. `--limit-train-samples` and `--limit-val-samples` cap only their respective splits for short tests. `--log-every` prints the first batch, every Nth batch, and the last batch, including a start line so slow CPU batches show that they are running.

Short CPU performance check from the project root:

```powershell
python -m ml.train_baseline --epochs 1 --image-size 128 --batch-size 1 --cpu-threads 2 --limit-train-samples 4 --limit-val-samples 2 --output-dir ml/performance-test
```

Use a separate output directory for this check so its smoke checkpoint is not mistaken for a full baseline checkpoint. The command does not load the test split.
