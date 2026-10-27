from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, owned_or_admin
from app.db.session import get_db
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.user import User

router = APIRouter(tags=["analysis"])


@router.post("/cases/{case_id}/analysis-runs", status_code=503)
def start_analysis(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "code": "analysis_unavailable",
        "detail": "No inference model is configured. No analysis was run and no results were generated.",
    }


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    query = select(AnalysisRun).join(Case, Case.id == AnalysisRun.case_id).where(AnalysisRun.id == run_id)
    if current_user.role != "admin":
        query = query.where(Case.owner_id == current_user.id)
    if db.scalar(query) is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    raise HTTPException(status_code=503, detail="Analysis status is unavailable until a real inference service is integrated")


@router.get("/analysis-runs/{run_id}/results", status_code=503)
def get_analysis_results(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    query = select(AnalysisRun).join(Case, Case.id == AnalysisRun.case_id).where(AnalysisRun.id == run_id)
    if current_user.role != "admin":
        query = query.where(Case.owner_id == current_user.id)
    if db.scalar(query) is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return {"code": "results_unavailable", "detail": "No model output is available; no findings or measurements were generated."}
