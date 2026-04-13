import time
import logging
from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .models import Base, ScheduledJob, JobRun, Client
from .scheduler import schedule_jobs_for_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BACKOFF_MINUTES = [1, 5, 30]
ALERT_URL = "https://httpbin.org/post"
REMINDER_URL = "https://httpbin.org/post"

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_tables():
    Base.metadata.create_all(bind=engine)


def seed_clients(db: Session):
    if db.query(Client).count() > 0:
        return
    import uuid
    clients = [
        Client(id=uuid.uuid4(), name="ТОО Ромашка",     timezone="Asia/Almaty",   billing_day=5,  monthly_fee=25000),
        Client(id=uuid.uuid4(), name="ИП Иванов",       timezone="Asia/Almaty",   billing_day=15, monthly_fee=10000),
        Client(id=uuid.uuid4(), name="ТОО Астана Плюс", timezone="Asia/Almaty",   billing_day=1,  monthly_fee=50000),
        Client(id=uuid.uuid4(), name="ООО МосТех",      timezone="Europe/Moscow", billing_day=10, monthly_fee=75000),
    ]
    db.add_all(clients)
    db.commit()
    log.info(f"Создано {len(clients)} тестовых клиентов")


def run_job(db: Session, job: ScheduledJob):
    started = datetime.now(timezone.utc)
    run = JobRun(job_id=job.id, started_at=started, result="FAILED")
    db.add(run)

    try:
        if job.job_type == "GENERATE_INVOICE":
            log.info(f"[{job.client_id}] Генерируем счёт за {job.target_date.strftime('%Y-%m')}")

        elif job.job_type == "SEND_REMINDER":
            log.info(f"[{job.client_id}] Отправляем напоминание")
            httpx.post(REMINDER_URL, json={
                "client_id": str(job.client_id),
                "job_id": str(job.id),
                "message": "Напоминание об оплате счёта"
            }, timeout=5)

        elif job.job_type == "BLOCK_SERVICE":
            log.info(f"[{job.client_id}] Блокируем сервис (PAUSED)")
            client = db.query(Client).filter(Client.id == job.client_id).first()
            if client and client.status == "ACTIVE":
                client.status = "PAUSED"

        run.result = "SUCCESS"
        run.finished_at = datetime.now(timezone.utc)
        job.status = "SUCCESS"
        db.commit()
        log.info(f"Задача {job.job_type} [{job.id}] — SUCCESS")

    except Exception as e:
        db.rollback()
        run.result = "FAILED"
        run.error_message = str(e)
        run.finished_at = datetime.now(timezone.utc)
        job.retry_count += 1

        if job.retry_count >= 3:
            job.status = "FAILED"
            try:
                httpx.post(ALERT_URL, json={
                    "alert": "job_failed",
                    "job_id": str(job.id),
                    "job_type": job.job_type,
                    "client_id": str(job.client_id),
                    "error": str(e)
                }, timeout=5)
            except Exception:
                pass
            log.error(f"Задача {job.id} провалилась 3 раза — алерт отправлен")
        else:
            delay = BACKOFF_MINUTES[job.retry_count - 1]
            job.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=delay)
            job.status = "PENDING"
            log.warning(f"Задача {job.id} упала, retry через {delay} мин")

        db.add(run)
        db.add(job)
        db.commit()


def tick(db: Session):
    from datetime import timezone
    now = datetime.now(timezone.utc)

    clients = db.query(Client).filter(Client.status == "ACTIVE").all()
    for client in clients:
        for delta in [0, 1]:
            month = now.month + delta
            year = now.year + (1 if month > 12 else 0)
            month = month if month <= 12 else month - 12
            schedule_jobs_for_client(db, client, year, month)

    pending_jobs = (
        db.query(ScheduledJob)
        .filter(
            ScheduledJob.status == "PENDING",
            ScheduledJob.next_run_at <= now
        )
        .all()
    )

    if pending_jobs:
        log.info(f"Нашли {len(pending_jobs)} задач для выполнения")

    for job in pending_jobs:
        job.status = "RUNNING"
        db.commit()
        run_job(db, job)


def main():
    log.info("Воркер запущен")
    create_tables()
    db = SessionLocal()
    seed_clients(db)

    while True:
        try:
            tick(db)
        except Exception as e:
            log.error(f"Ошибка в тике воркера: {e}")
        time.sleep(60)


if __name__ == "__main__":
    main()