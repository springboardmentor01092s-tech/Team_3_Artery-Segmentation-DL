# Segmentation Performance Report

## 1. Project Overview

- **Project:** Artery Segmentation and Stenosis Detection
- **Dataset:** ARCADE Coronary Angiography
- **Image Size:** 256 × 256 pixels

## 2. Training Configuration

| Parameter | Value |
|---|---|
| Training Images | 1,000 |
| Validation Images | 200 |
| Test Images | 300 |
| Training Epochs | 30 |
| Batch Size | 2 |
| Optimizer | Adam |
| Learning Rate | 0.0001 |
| Loss Function | 0.5 BCEWithLogitsLoss + 0.5 DiceLoss |

## 3. Model Performance Comparison

| Metric | Baseline U-Net | Attention U-Net |
|---|---:|---:|
| Best Validation Epoch | 13 | 12 |
| Best Validation Dice | 79.71% | 80.52% |
| Test Dice | 75.59%* | 75.97% |

*Baseline U-Net test Dice is a previously reported result and has not been reproduced using the recovered checkpoint.*

### Attention U-Net Test Results

- Test Images: 300
- Test Dice: 75.97%
- Mean Batch BCE Loss: 0.07152

## 4. Performance Analysis

Attention U-Net achieved a validation Dice score of 80.52%, compared with 79.71% for Baseline U-Net.

Its recorded test Dice score was 75.97%, compared with the previously reported 75.59% for Baseline U-Net.

This represents a 0.38 percentage-point improvement in the recorded test Dice.

The improvement is relatively small, and the baseline checkpoint must be re-evaluated on the same test set before making a definitive model-selection decision.

## 5. Conclusion

Based on the currently available evaluation reports, Attention U-Net demonstrates slightly better recorded segmentation performance than Baseline U-Net.

Attention U-Net is the current preferred candidate, subject to a reproducible baseline comparison.

## 6. Limitations

- Baseline U-Net test performance has not been reproduced using its recovered checkpoint.
- Comparable test results for all metrics are not currently available.
- The results represent research evaluation on the ARCADE dataset and do not establish clinical validity.

## 7. Supporting Reports

- baseline_training_report.json
- attention_unet_training_report.json
- attention_unet_test_report.json
- combined_training_comparison.json
- combined_training_comparison.txt