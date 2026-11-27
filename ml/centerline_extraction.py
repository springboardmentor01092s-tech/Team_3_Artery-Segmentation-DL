
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize


def connect_nearby_endpoints(
    centerline: np.ndarray,
    max_distance: float = 3.0,
) -> np.ndarray:
    """Connect nearby skeleton endpoints without discarding existing branches."""
    skeleton = centerline.astype(bool).copy()

    # Endpoints have exactly one neighbor in their 8-pixel neighborhood.
    neighbors = ndimage.convolve(
        skeleton.astype(np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        mode="constant",
        cval=0,
    ) - skeleton.astype(np.uint8)

    endpoints = np.argwhere(skeleton & (neighbors == 1))
    if len(endpoints) < 2:
        return skeleton

    # Connect only endpoint pairs that are close and do not already share a path.
    candidates = []
    for i in range(len(endpoints)):
        for j in range(i + 1, len(endpoints)):
            distance = np.linalg.norm(endpoints[i] - endpoints[j])
            if 1 < distance <= max_distance:
                candidates.append((distance, i, j))

    candidates.sort()
    used = set()

    for _, i, j in candidates:
        if i in used or j in used:
            continue

        y1, x1 = endpoints[i]
        y2, x2 = endpoints[j]

        # Draw a short straight bridge between the endpoints.
        steps = max(abs(y2 - y1), abs(x2 - x1))
        ys = np.rint(np.linspace(y1, y2, steps + 1)).astype(int)
        xs = np.rint(np.linspace(x1, x2, steps + 1)).astype(int)

        skeleton[ys, xs] = True
        used.update((i, j))

    return skeleton


def extract_centerline(mask: np.ndarray) -> np.ndarray:
    """
    Extract the centerline of an artery from a binary segmentation mask.

    Args:
        mask: A 2D array where artery pixels are non-zero.

    Returns:
        A boolean 2D array representing the artery centerline.
    """
    if mask.ndim != 2:
        raise ValueError("Expected a 2D artery segmentation mask.")

    binary_mask = mask > 0

    if not np.any(binary_mask):
        raise ValueError("The segmentation mask contains no artery pixels.")

    centerline = skeletonize(binary_mask)

    return centerline


def process_mask(input_path: str, output_path: str) -> None:
    """Load a segmentation mask, extract its centerline, and save the result."""
    mask_image = Image.open(input_path).convert("L")
    mask = np.array(mask_image)

    centerline = extract_centerline(mask)

    output = (centerline.astype(np.uint8) * 255)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output).save(output_path)

    print(f"Centerline saved to: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract an artery centerline from a binary mask."
    )
    parser.add_argument("--input", required=True, help="Path to the binary mask")
    parser.add_argument("--output", required=True, help="Path for the centerline image")
    args = parser.parse_args()

    process_mask(args.input, args.output)
