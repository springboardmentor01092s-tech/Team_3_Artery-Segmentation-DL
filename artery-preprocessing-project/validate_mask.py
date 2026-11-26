
import cv2
import numpy as np
from pathlib import Path

image_path = Path(
    r"C:\Users\aksha\Downloads\arcade\syntax\train\images\91.png"
)
mask_path = Path(
    r"C:\Users\aksha\Downloads\arcade\syntax\train\masks\91_mask.png"
)

output_path = Path("91_validation_overlay.png")

image = cv2.imread(str(image_path))
mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

if image is None or mask is None:
    raise FileNotFoundError("Check the image and mask paths.")

if image.shape[:2] != mask.shape[:2]:
    mask = cv2.resize(
        mask,
        (image.shape[1], image.shape[0]),
        interpolation=cv2.INTER_NEAREST
    )

overlay = image.copy()
overlay[mask > 0] = (
    0.5 * overlay[mask > 0] +
    0.5 * np.array([0, 255, 0])
).astype(np.uint8)

cv2.imwrite(str(output_path), overlay)
print("Saved overlay:", output_path.resolve())
