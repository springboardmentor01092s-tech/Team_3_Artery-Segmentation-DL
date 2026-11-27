
from pathlib import Path
import argparse
import csv

import numpy as np
from PIL import Image
from scipy import ndimage


def estimate_vessel_diameter(
    mask: np.ndarray,
    centerline: np.ndarray
) -> np.ndarray:
    """
    Estimate local vessel diameter at every centerline pixel.

    Returns:
        Array containing estimated diameters in pixels.
    """

    if mask.ndim != 2 or centerline.ndim != 2:
        raise ValueError("Mask and centerline must be 2D arrays.")

    if mask.shape != centerline.shape:
        raise ValueError("Mask and centerline dimensions must match.")

    binary_mask = mask > 0
    skeleton = centerline > 0

    if not np.any(binary_mask):
        raise ValueError("Empty artery mask.")

    if not np.any(skeleton):
        raise ValueError("Empty centerline.")

    if np.any(skeleton & ~binary_mask):
        raise ValueError("Centerline contains pixels outside the artery mask.")

    # Calculate distance from each artery pixel to the nearest background pixel.
    distance_map = ndimage.distance_transform_edt(binary_mask)

    # Get distance values only at centerline locations.
    radii = distance_map[skeleton]

    # Diameter is approximately twice the local radius.
    diameters = 2.0 * radii

    return diameters


def process_diameter(mask_path: str, centerline_path: str,
                     output_path: str) -> None:

    mask = np.array(Image.open(mask_path).convert("L"))
    centerline = np.array(Image.open(centerline_path).convert("L"))

    diameters = estimate_vessel_diameter(mask, centerline)

    coordinates = np.argwhere(centerline > 0)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save measurements for every centerline pixel.
    with open(output_path, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["row", "column", "diameter_pixels"])

        for (y, x), diameter in zip(coordinates, diameters):
            writer.writerow([y, x, round(float(diameter), 2)])

    print("Vessel diameter estimation completed.")
    print("Total measurement points:", len(diameters))
    print("Minimum diameter:", round(float(diameters.min()), 2), "pixels")
    print("Maximum diameter:", round(float(diameters.max()), 2), "pixels")
    print("Mean diameter:", round(float(diameters.mean()), 2), "pixels")
    print("Results saved to:", output_path)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Estimate artery diameter along its centerline."
    )

    parser.add_argument("--mask", required=True)
    parser.add_argument("--centerline", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    process_diameter(
        args.mask,
        args.centerline,
        args.output
    )
