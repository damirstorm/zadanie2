import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Numeric,
    DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    timezone = Column(String, nullable=False)   # "Asia/Almaty", "Europe/Moscow"
    billing_day = Column(Integer, nullable=False)  # 1–28, день месяца для выставления счёта
    monthly_fee = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE | PAUSED | TERMINATED

    jobs = relationship("ScheduledJob", back_populates="client")


class ScheduledJob(Base):
    """
    Одна запись = одна задача для клиента на конкретную дату.

    ИДЕМПОТЕНТНОСТЬ: уникальный индекс (client_id, job_type, target_date)
    гарантирует, что даже если воркер упал и перезапустился —
    повторный INSERT просто упадёт с ошибкой конфликта, дубля не будет.
    """
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    job_type = Column(String, nullable=False)
    # GENERATE_INVOICE | SEND_REMINDER | BLOCK_SERVICE

    target_date = Column(DateTime(timezone=True), nullable=False)
    # Когда задача должна выполниться (хранится в UTC)

    status = Column(String, nullable=False, default="PENDING")
    # PENDING | RUNNING | SUCCESS | FAILED | CANCELLED

    retry_count = Column(Integer, default=0)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    # null = запустить как можно скорее, иначе — ждать до этого времени (для retry)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    client = relationship("Client", back_populates="jobs")
    runs = relationship("JobRun", back_populates="job", order_by="JobRun.started_at")

    __table_args__ = (
        # Главная гарантия идемпотентности на уровне БД
        UniqueConstraint("client_id", "job_type", "target_date", name="uq_job_per_client_date"),
        # Индекс для воркера — он ищет задачи по status + next_run_at
        Index("ix_jobs_status_next_run", "status", "next_run_at"),
    )


class JobRun(Base):
    """История каждой попытки выполнения задачи."""
    __tablename__ = "job_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_jobs.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(String, nullable=False)       # SUCCESS | FAILED
    error_message = Column(String, nullable=True)

    job = relationship("ScheduledJob", back_populates="runs")