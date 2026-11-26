# Artery Segmentation Research Application

This is the single application in `artery-preprocessing-project`. It keeps the original React interface and FastAPI case, authentication, upload, and preprocessing system, and adds ARCADE stenosis segmentation inference, candidate visualization, optional Integrated Gradients attribution, history, model metadata comparison, and reports.

The application provides research model outputs. It does not diagnose disease or assign clinical severity. Image-derived percentage narrowing remains unavailable because the model and ARCADE annotations do not provide validated lumen boundaries, reference/minimum lumen diameters, or verified image calibration. A separate geometry utility can measure pixel widths from externally supplied expert-validated lumen masks, but normal inference does not produce or consume such masks; millimetre conversion and percentage remain gated on validated physical calibration and reference measurements. On-demand Integrated Gradients can highlight input sensitivity for a recorded lesion analysis when its exact checkpoint is still available; this attribution is not clinically validated and is not a diagnostic confidence. The segmentation overlay and probability heatmap visualize model outputs but are not Grad-CAM.

## Backend setup (Windows PowerShell)

Run these commands from the application root (the folder containing `backend` and `frontend`):

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend\.env`: set a long random `SECRET_KEY`; leave `DATABASE_URL` as `sqlite:///./artery_preprocessing.db` for the existing local database; leave upload/processed/analysis paths at their defaults unless you intentionally want different storage. The backend creates missing tables and folders at startup without dropping existing tables or rows.

Application logs use a rotating UTF-8 file at `backend\logs\artery-preprocessing.log` by default. Configure `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT` in `backend\.env` to change the level, destination, size limit, and retained rotations. The defaults allow the active log plus five 5 MiB rotated files (about 30 MiB maximum). HTTP telemetry records route templates, status and duration without request bodies or query values. `GET /api/health` performs a database readiness probe and returns 503 when that dependency is unavailable. Use a protected local directory and do not log credentials, tokens, or patient-identifying information. This is a local file sink; centralized production log shipping and retention policies are not configured.

Create an administrator account if one does not already exist, then start the API:

```powershell
python -m app.scripts.create_admin --email "admin@example.com" --password "use-a-strong-local-password" --name "Local Administrator"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: http://127.0.0.1:8000/docs

For schema-managed installations, back up the database, then run `alembic upgrade head`. The migration chain handles a fresh database and can add missing application tables to a legacy, unstamped database without dropping existing tables or rows. It does not alter columns in tables that already exist; review the target schema before using Alembic on a customized production database. The app also runs additive `create_all` at startup; do not delete the SQLite database to initialize features.

## Frontend setup

Open another PowerShell terminal at the application root:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. `frontend\.env` sets `VITE_API_URL=http://127.0.0.1:8000` for local development.

The authenticated navigation includes Dashboard, Cases, Image upload, Preprocessing, Analysis history, Reports, and Model comparison. Dataset inspection is limited to data scientists and administrators; user management and audit logs are administrator-only. Upload selects an accessible case and previews PNG/JPEG locally before submission. History is scoped by the backend to cases available to the signed-in user. Reports call the existing case-scoped PDF/CSV/JSON endpoints. Model comparison displays checkpoint metadata and saved evaluations only; it does not start training or imply absent results. See [the user guide](docs/user_guide.md) and [frontend/API route mapping](docs/api_documentation.md#react-application-routes).

## Model and dataset

- The integrated checkpoint is `backend\checkpoints\best_stenosis_unet_optimized.pth`; the original checkpoint in `complete_project` was read-only and was not overwritten.
- The active validation-selected threshold (0.55) is stored separately in `backend\checkpoints\best_stenosis_unet_optimized.pth.threshold.json`; the checkpoint weights are unchanged. A byte-identical pre-improvement backup is kept beside it.
- `MODEL_CHECKPOINT` can override that path in `backend\.env` (relative paths resolve from `backend`). A missing or unreadable checkpoint is reported as unavailable; analysis requests return a clear service error.
- Checkpoints with a `smp_` architecture require the optional packages in `backend\requirements-ml.txt`. The loader builds them from stored architecture/encoder metadata and uses the stored `normalization` mode; pretrained encoder weights are not downloaded during checkpoint loading.
- Dashboard model comparison uses saved full-validation evaluations when available; stored checkpoint metrics are kept separate from new evaluation results.
- The ARCADE source is not copied or modified. The default `ARCADE_ROOT` resolves to the parent containing `stenosis\` and `syntax\`; set `ARCADE_ROOT` in `backend\.env` for another dataset location. For Kaggle, point it at the mounted dataset directory containing `stenosis/` and `syntax/` (confirm the exact mounted path in the notebook before training). COCO parsing and dataset-loader utilities are in `backend\app\arcade_ml`.
- Inference accepts supported single-frame PNG/JPEG/DICOM uploads, converts a working copy to the model input, and preserves the uploaded original. Multi-frame DICOM remains unsupported.

## Audit, evaluate, and train

From the backend directory with its virtual environment active:

```powershell
python -m app.arcade_ml.audit_validation
```

This audits train and validation integrity (not test), evaluates the configured checkpoint on validation, selects a threshold using validation only, and writes per-image CSV, metrics JSON, resource measurements, post-processing comparisons, and 50 representative visual comparisons under `reports\model_validation`. A historical `dataset_audit.json` from the earlier full integrity audit is retained; new routine runs write `dataset_audit_train_val.json`.

The experiment runner supports `resunet`, `unet`, and `attention_unet`; losses `bce_dice` and `tversky`; and optimizers `adamw` and `adam`. It writes a uniquely named checkpoint, configuration, epoch history, and training graphs; it does not overwrite the active checkpoint. Example:

```powershell
python -m app.arcade_ml.train_experiment --architecture resunet --loss bce_dice --optimizer adamw --epochs 8 --batch-size 4 --base-channels 16 --image-size 256 --pos-weight 5 --seed 20261124
```

The runner also supports `smp_unet`, `smp_unetplusplus`, and `smp_deeplabv3plus` with optional encoder initialization, `focal` and `focal_tversky` losses, AMP, gradient accumulation, cosine scheduling, conservative paired augmentation, and foreground-aware image sampling. Those SMP architectures were added for the Kaggle workflow but have not yet been trained locally. Do not spend extended time on them using this CPU-only machine.

Then evaluate the experiment checkpoint explicitly:

```powershell
python -m app.arcade_ml.audit_validation --checkpoint checkpoints\resunet16_stenosis_experiment.pth
```

See [the completed validation report](docs/model_validation_report.md) for this machine's results and limitations.

## Kaggle GPU experiments

The local machine has no CUDA GPU. The private train/validation input and code input have already been uploaded, and the existing Kaggle kernel is `drajuakshayarao/arcade-gpu-model-sweep-2026-11-24`. Version 1 failed because Kaggle expanded the uploaded code archive into `backend/...` files while the notebook expected a ZIP. Version 2 handles both layouts and was submitted to the same kernel; its last recorded state was `QUEUED`. Do not create another kernel or upload the datasets again. Check its status before relying on any training result.

After Kaggle reports successful completion, retrieve and compare its output from the project root:

```powershell
$env:KAGGLE_CONFIG_DIR = Join-Path $env:USERPROFILE '.kaggle'
python .\notebooks\collect_kaggle_results.py
```

The collector checks full validation coverage and test-split flags and writes a baseline comparison. It does not promote a checkpoint. Follow [the post-run handoff](reports/kaggle_gpu_run/POST_RUN_HANDOFF.md) to revalidate a candidate using train/validation-only data and run app inference before considering integration. The notebook itself uses validation only for selection and never opens test files.

The notebook uses ImageNet normalization for pretrained SMP encoders. That normalization is stored in the checkpoint and used by app inference. If an SMP model wins, install `backend\requirements-ml.txt` in the application virtual environment before loading that checkpoint. Keep the old active checkpoint until the transferred model passes local inference and API/export checks.

## Existing tests and checks

```powershell
Set-Location .\backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

## Project documentation

- [Project requirement checklist](docs/project_requirement_checklist.md): milestone-level implementation status and evidence.
- [Final completion audit](docs/final_completion_audit.md): current completion, blockers, and preservation notes.
- [Project report](docs/project_report.md) and [presentation outline](docs/project_presentation.md).
- [User guide](docs/user_guide.md), [API documentation](docs/api_documentation.md), and [database schema](docs/database_schema.md).
- [Uploaded case ground-truth comparison](docs/ground_truth_comparison.md), including exact annotation identity, metrics, per-candidate overlap and visualization.

```powershell
Set-Location .\frontend
npm test
npm run build
```

Tests use an in-memory database and temporary storage. They do not clear the existing database or uploaded files.

## Storage and deployment notes

The database remains `backend\artery_preprocessing.db`; originals, preprocessing outputs, and analysis visualizations remain under `backend\uploads`, `backend\processed`, and `backend\analysis`. Back up the database and those directories together before moving or deploying the app. Keep `.env` secret and never expose private storage as static frontend assets. Production mode rejects development/example/short JWT secrets and requires explicit HTTPS CORS origins that are not local hosts. For deployment, use HTTPS, a strong secret, a production ASGI process, restricted CORS origins, protected persistent storage, and a managed database with backups. Local development settings are not production settings.
