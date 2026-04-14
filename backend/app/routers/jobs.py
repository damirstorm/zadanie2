from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from uuid import UUID
from ..database import get_db
from ..models import ScheduledJob
from ..schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/upcoming", response_model=list[JobOut])
def upcoming_jobs(db: Session = Depends(get_db)):
    """План на 7 дней вперёд."""
    now = datetime.utcnow()
    week_later = now + timedelta(days=7)
    return (
        db.query(ScheduledJob)
        .filter(
            ScheduledJob.target_date >= now,
            ScheduledJob.target_date <= week_later,
            ScheduledJob.status != "CANCELLED"
        )
        .order_by(ScheduledJob.target_date)
        .all()
    )


@router.get("/history", response_model=list[JobOut])
def history_jobs(
    status: str = None,
    job_type: str = None,
    db: Session = Depends(get_db)
):
    """История за 30 дней с фильтрами по статусу и типу."""
    since = datetime.utcnow() - timedelta(days=30)
    q = db.query(ScheduledJob).filter(ScheduledJob.target_date >= since)
    if status:
        q = q.filter(ScheduledJob.status == status)
    if job_type:
        q = q.filter(ScheduledJob.job_type == job_type)
    return q.order_by(ScheduledJob.target_date.desc()).all()


@router.post("/{job_id}/run-now")
def run_now(job_id: UUID, db: Session = Depends(get_db)):  # ← UUID вместо str
    """Ручной запуск задачи немедленно."""
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status not in ("PENDING", "FAILED"):
        raise HTTPException(status_code=400, detail=f"Нельзя запустить задачу со статусом {job.status}")
    job.next_run_at = datetime.utcnow()
    job.status = "PENDING"
    job.retry_count = 0
    db.commit()
    return {"ok": True, "message": "Задача поставлена в очередь на немедленный запуск"}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: UUID, db: Session = Depends(get_db)):  # ← UUID вместо str
    """Отмена задачи из плана."""
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status != "PENDING":
        raise HTTPException(status_code=400, detail="Можно отменить только PENDING задачу")
    job.status = "CANCELLED"
    db.commit()
    return {"ok": True}