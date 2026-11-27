# Artery Segmentation and Stenosis Detection Using Advanced DL Techniques

An AI-assisted research and decision-support prototype for artery segmentation, stenosis-region segmentation/localization, exploratory narrowing analysis, explainability, and medical-image visualization.

> **Research prototype only:** This project is not an autonomous diagnostic system. It has not been clinically validated. Predicted masks, candidate regions, severity labels, Grad-CAM overlays, and narrowing estimates must not be treated as confirmed clinical findings.

## Project overview

The project follows the four milestones defined in the Infosys Springboard internship brief:

1. **Milestone 1 — Project setup:** dataset selection and exploration, application architecture, frontend/backend, authentication, image upload, and preprocessing.
2. **Milestone 2 — Artery segmentation:** baseline and attention-based segmentation, mask generation, post-processing, vessel analysis, and evaluation.
3. **Milestone 3 — Stenosis analysis:** stenosis-region segmentation/localization, exploratory narrowing and severity estimates, explainability, and visualization.
4. **Milestone 4 — Integration and delivery:** dashboard and reporting features, exports, testing, Docker/deployment work, monitoring/logging, and documentation.

## Main technology stack

- **Frontend:** React 19, Vite 8, TypeScript, React Router
- **Backend:** FastAPI, Python, Pydantic
- **Database:** PostgreSQL
- **ORM and migrations:** SQLAlchemy 2, Alembic
- **Database driver:** Psycopg 3
- **Machine learning:** PyTorch and `segmentation-models-pytorch`
- **Model architectures:** U-Net, Attention U-Net, and U-Net++ with a ResNet34 encoder
- **Containerization:** Docker Compose

## Repository structure

```text
.
├── backend/                 FastAPI application, API endpoints, services,
│                            database models, migrations, and tests
├── src/                     React frontend, routes, pages, components,
│                            API integration, and styles
├── ml/                      Model definitions, inference/training utilities,
│                            tests, and model checkpoint locations
│   ├── models/
│   ├── inference/
│   └── checkpoints/
├── public/                  Static frontend assets
├── design-references/       UI reference material
├── research_reference/      Project research/reference material
├── handover_package/        Project handover/documentation material
├── compose.yaml             Docker Compose configuration
├── package.json             Frontend scripts and dependencies
└── README.md
```

Some generated files, local datasets, uploaded images, runtime storage, environment files, and development caches are intentionally not tracked in Git.

## Dataset

The experiments use the **ARCADE coronary angiography** dataset, consisting of PNG images and COCO JSON annotations.

Recorded dataset split:

| Split | Images | Stenosis annotations |
|---|---:|---:|
| Train | 1,000 | 1,625 |
| Validation | 200 | 406 |
| Test | 300 | 386 |
| **Total** | **1,500** | **2,417** |

The stenosis category is recorded as `category_id = 26` (`stenosis`).

The dataset does not provide validated severity labels, physical pixel calibration, or validated reference/minimum lumen diameters. Dataset access and licensing/usage conditions must be checked at the original dataset source before redistribution. The dataset itself is not included in this repository.

## Model experiments and recorded results

### Artery segmentation

Two artery segmentation models were trained at 256 × 256 resolution.

| Model | Best validation Dice | Test Dice | Role |
|---|---:|---:|---|
| Baseline U-Net | 79.71% | 75.59% | Comparison baseline |
| **Attention U-Net** | **80.52%** | **75.97%** | Selected artery segmentation model |

Attention U-Net was selected because its recorded validation and test Dice scores were slightly higher than the baseline U-Net.

### Stenosis segmentation

The stenosis segmentation experiment uses **U-Net++ with a ResNet34 encoder**, one grayscale input channel, one output channel, and 512 × 512 input resolution.

Recorded test results at threshold 0.50:

| Metric | Result |
|---|---:|
| Dice | 50.69% |
| IoU | 36.60% |
| Precision | 53.82% |
| Recall | 56.34% |
| Specificity | 99.56% |

A separate threshold analysis recorded a provisional validation threshold of 0.20 for new website inference. Historical Kaggle Task 7/8 outputs used threshold 0.10. These thresholds belong to different experiment/integration contexts and should not be conflated.

These are historical experiment results, not a claim of clinical performance or fresh reproduction from this repository.

## Model checkpoints

Large model checkpoints are stored using **Git Large File Storage (Git LFS)**.

The repository tracks six checkpoint files:

| Checkpoint | Repository path |
|---|---|
| Attention U-Net | `ml/checkpoints/best_attention_unet.pt` |
| Baseline artery U-Net | `ml/performance-test/checkpoints/best_unet.pt` |
| Standard stenosis U-Net++ best | `ml/checkpoints/stenosis/standard_unetpp/best_unetpp.pt` |
| Standard stenosis U-Net++ last | `ml/checkpoints/stenosis/standard_unetpp/last_checkpoint.pt` |
| Focal Tversky U-Net++ best | `ml/checkpoints/stenosis/focal_tversky/best_focal_tversky.pt` |
| Focal Tversky U-Net++ last | `ml/checkpoints/stenosis/focal_tversky/last_checkpoint.pt` |

Install Git LFS before cloning/downloading model artifacts:

```bash
git lfs install
git clone https://github.com/springboardmentor01092s-tech/Team_3_Artery-Segmentation-DL.git
cd Team_3_Artery-Segmentation-DL
git lfs pull
```

If a checkpoint appears as a small text pointer instead of a model file, run `git lfs pull` after Git LFS is installed.

## Application capabilities

The application codebase includes:

- Authentication and protected application routes
- Role-aware access, including administrator-managed accounts
- Patient and case management
- Authenticated medical-image upload and preview
- Image preprocessing workflow and persisted preprocessing metadata
- Analysis workflow and result presentation
- Artery/stenosis segmentation artifacts and candidate visualization
- Grad-CAM model-explanation visualization
- Dashboard, reports, and export-related functionality

The exact availability of each workflow depends on the current branch and deployment configuration. Do not assume a feature is clinically validated merely because it is displayed in the UI.

## Local development

### Prerequisites

- Git
- Git LFS
- Node.js and npm
- Python version compatible with the backend dependency files
- Docker Desktop with Docker Compose
- PostgreSQL (or the repository's Compose database service)

### Frontend

From the repository root:

```bash
npm ci
npm run dev
```

The Vite development server normally runs at `http://localhost:5173`.

### Backend

Backend dependencies and environment variables are managed separately under `backend/`. Start by reviewing:

- `backend/README.md`
- `backend/requirements.txt`
- `backend/.env.example`
- `backend/.postgres.env.example`

Create local environment files from the example files and fill in local values. **Do not commit real `.env` files, passwords, tokens, or database credentials.**

Apply migrations and start the API using the instructions in `backend/README.md`. The documented local API address is `http://127.0.0.1:8000`; interactive API documentation is normally available at `http://127.0.0.1:8000/docs`.

### Docker Compose

Review `compose.yaml` and the environment example files before starting services. Preserve the named PostgreSQL data volume. **Do not use `docker compose down -v`**, because it removes named volumes and can delete database data.

## Testing and verification

The project contains frontend, backend, and ML-related tests. Run the test commands documented in the relevant package and backend files for the branch being used.

A previously recorded API test run reported **48 passed, 0 failed, and 1 skipped** in a Windows test environment using in-memory SQLite and mocked inference. This is not a complete production end-to-end test or clinical validation.

Build/test results can change as code changes. Re-run relevant checks before releases and record the actual command output.

## Git branches

The repository has these relevant branches:

- `main` — default branch
- `lakshya` — personal development branch
- `Review` — review branch created from `lakshya`

At the 27 November 2026 handover, `Review` and `lakshya` both pointed to commit `cc4d837` and contained the same project snapshot.

**Important:** Future commits pushed to `lakshya` do not automatically appear in `Review`. Merge or otherwise deliberately integrate changes when the review branch needs updating.

Check the current branch before making changes:

```bash
git branch --show-current
git status
```

## Important limitations and responsible use

- This is an academic research/decision-support prototype, not an autonomous diagnostic system.
- No clinical validation has been performed.
- Predicted segmentation masks and candidate regions are not confirmed stenoses.
- Severity classification and percentage narrowing are experimental.
- Pixel-based widths are not physically calibrated lumen measurements.
- The dataset does not provide validated severity labels or physical pixel spacing.
- Grad-CAM is a visualization of model behavior, not a ground-truth lesion boundary or proof of model correctness.
- Model probabilities are not calibrated clinical confidence scores.
- Historical experiment metrics should not be presented as current clinical performance.

## Security and data handling

- Never commit credentials, `.env` files, tokens, private keys, or database passwords.
- Do not commit patient-identifiable information or private uploaded medical images.
- Do not add raw datasets, database dumps, local storage, or runtime uploads to public source control.
- Keep model artifacts under the repository's Git LFS rules.
- Preserve database migrations and persistent volumes.
- Review `.gitignore` and `.gitattributes` before adding large or sensitive files.

## Project status and further work

The repository contains the application, ML code, experiment artifacts, and model checkpoints. Remaining verification and delivery activities should be tracked against the official internship Milestone 4 requirements, including comprehensive end-to-end testing, security/performance testing, deployment verification, monitoring/logging review, final documentation, and presentation.

Update this README when a milestone is actually completed and verified. Do not mark planned work as complete without execution evidence.

---

**Internship project:** Infosys Springboard AI Internship  
**Project title:** Artery Segmentation and Stenosis Detection Using Advanced DL Techniques
