from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import Client, ScheduledJob


def get_billing_datetime_utc(client: Client, year: int, month: int) -> datetime:
    """
    Возвращает момент выставления счёта в UTC.
    Например: billing_day=5, timezone=Asia/Almaty →
    2026-05-05 00:00:00+05:00 → 2026-05-04 19:00:00 UTC
    """
    tz = pytz.timezone(client.timezone)
    local_dt = tz.localize(datetime(year, month, client.billing_day, 0, 0, 0))
    return local_dt.astimezone(pytz.utc).replace(tzinfo=None)


def schedule_jobs_for_client(db: Session, client: Client, year: int, month: int):
    """
    Создаёт три задачи для клиента на указанный месяц.
    Если задача уже существует — пропускаем (идемпотентность через UniqueConstraint).
    """
    invoice_dt = get_billing_datetime_utc(client, year, month)
    reminder_dt = invoice_dt + timedelta(days=7)
    block_dt = invoice_dt + timedelta(days=30)

    jobs_to_create = [
        ScheduledJob(
            client_id=client.id,
            job_type="GENERATE_INVOICE",
            target_date=invoice_dt,
            next_run_at=invoice_dt,
        ),
        ScheduledJob(
            client_id=client.id,
            job_type="SEND_REMINDER",
            target_date=reminder_dt,
            next_run_at=reminder_dt,
        ),
        ScheduledJob(
            client_id=client.id,
            job_type="BLOCK_SERVICE",
            target_date=block_dt,
            next_run_at=block_dt,
        ),
    ]

    for job in jobs_to_create:
        try:
            db.add(job)
            db.commit()
        except IntegrityError:
            # Задача уже существует — это нормально, просто пропускаем
            db.rollback()