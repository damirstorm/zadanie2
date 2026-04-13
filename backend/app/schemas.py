from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class ClientCreate(BaseModel):
    name: str
    timezone: str
    billing_day: int
    monthly_fee: float
    status: str = "ACTIVE"


class ClientOut(ClientCreate):
    id: uuid.UUID
    class Config:
        from_attributes = True


class JobRunOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: Optional[datetime]
    result: str
    error_message: Optional[str]
    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    job_type: str
    target_date: datetime
    status: str
    retry_count: int
    next_run_at: Optional[datetime]
    created_at: datetime
    runs: List[JobRunOut] = []
    class Config:
        from_attributes = True