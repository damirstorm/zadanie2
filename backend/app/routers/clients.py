from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Client
from ..schemas import ClientCreate, ClientOut
from ..scheduler import schedule_jobs_for_client
from datetime import datetime

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).all()


@router.post("/", response_model=ClientOut)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    # Сразу планируем задачи на текущий и следующий месяц
    now = datetime.utcnow()
    for delta in [0, 1]:
        month = now.month + delta
        year = now.year + (1 if month > 12 else 0)
        month = month if month <= 12 else month - 12
        schedule_jobs_for_client(db, client, year, month)
    return client