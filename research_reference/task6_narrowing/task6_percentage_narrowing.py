from pathlib import Path
import cv2
import numpy as np
import pandas as pd
from scipy import ndimage
from skimage.morphology import skeletonize

ARTERY_DIR = Path("/kaggle/working/task5_artery_masks")
STENOSIS_DIR = Path("/kaggle/working/task5_stenosis_masks")
OUTPUT_CSV = Path("/kaggle/working/task6_percentage_narrowing_results.csv")


def load_mask(path):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read mask: {path}")
    return image > 0


def estimate_measurements(artery, stenosis):
    if artery.shape != stenosis.shape:
        artery = cv2.resize(
            artery.astype(np.uint8),
            (stenosis.shape[1], stenosis.shape[0]),
            interpolation=cv2.INTER_NEAREST
        ) > 0

    if not artery.any():
        return None, None, None, "Empty artery mask"

    if not stenosis.any():
        return None, None, None, "No stenosis candidate"

    labels, count = ndimage.label(artery)
    overlaps = np.bincount(
        labels[stenosis & (labels > 0)],
        minlength=count + 1
    )

    if count == 0 or overlaps[1:].max(initial=0) == 0:
        return None, None, None, "No artery-stenosis overlap"

    selected_label = int(np.argmax(overlaps[1:]) + 1)
    artery_component = labels == selected_label

    centerline = skeletonize(artery_component)
    distance_map = ndimage.distance_transform_edt(artery_component)
    diameter_map = 2.0 * distance_map

    lesion_region = ndimage.binary_dilation(stenosis, iterations=5)

    lesion_widths = diameter_map[centerline & lesion_region]
    reference_widths = diameter_map[centerline & ~lesion_region]

    if len(lesion_widths) == 0:
        return None, None, None, "No lesion centerline points"

    if len(reference_widths) < 5:
        return None, None, None, "Insufficient reference points"

    minimum_diameter = float(np.min(lesion_widths))
    reference_diameter = float(np.median(reference_widths))

    if reference_diameter <= 0:
        return None, None, None, "Invalid reference diameter"

    narrowing = (
        (reference_diameter - minimum_diameter)
        / reference_diameter
    ) * 100

    narrowing = float(np.clip(narrowing, 0, 100))

    return (
        round(reference_diameter, 2),
        round(minimum_diameter, 2),
        round(narrowing, 2),
        "Experimental pixel-based estimate; validation required"
    )


def classify_severity(value):
    if value is None or not np.isfinite(value):
        return "Unclassified"
    if value == 0:
        return "Normal"
    if value < 50:
        return "Mild / Outside 3 target classes"
    if value < 70:
        return "Moderate"
    return "Critical"


def main():
    artery_files = {
        p.name.removesuffix("_artery_mask.png"): p
        for p in ARTERY_DIR.glob("*_artery_mask.png")
    }
    stenosis_files = {
        p.name.removesuffix("_stenosis_mask.png"): p
        for p in STENOSIS_DIR.glob("*_stenosis_mask.png")
    }

    common_ids = sorted(
        set(artery_files) & set(stenosis_files),
        key=lambda x: int(x)
    )

    results = []

    for image_id in common_ids:
        artery = load_mask(artery_files[image_id])
        stenosis = load_mask(stenosis_files[image_id])

        reference, minimum, narrowing, status = estimate_measurements(
            artery, stenosis
        )

        results.append({
            "image_id": image_id,
            "reference_diameter_pixels": reference,
            "minimum_diameter_pixels": minimum,
            "estimated_narrowing_percent": narrowing,
            "predicted_severity": classify_severity(narrowing),
            "assessment_status": status
        })

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)

    print("Images processed:", len(df))
    print(df)
    print("Saved:", OUTPUT_CSV)


if __name__ == "__main__":
    main()
