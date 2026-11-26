# Dataset directory

Place **de-identified public research images** here. Do not store real patient-identifiable files.

Expected layout:

```
data/
  sample_images/
    example.png
    example.jpg
    example.dcm
```

Supported formats in this prototype: PNG, JPEG, and single-frame DICOM.

The EDA notebook reads `DATASET_DIR` or defaults to `data/sample_images`. If the folder is empty, the notebook reports that no files were found instead of inventing statistics.

Public sources you may use (follow each source's license and de-identification rules):

- Educational DICOM samples from a public teaching archive
- Synthetic images generated locally with the seed script

The seed script writes `synthetic_vessel_like.png` for demonstration only.
