"""Verify database connection for storing/retrieving notification identifiers per project.

Connects to the verify database to read/write the extra_info JSON field
on the evaluation_jobs table. Supports both Telegram chat_id and WhatsApp phone.
"""

import json
import logging
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def init_engine(host: str, port: int, user: str, password: str, db_name: str) -> None:
    """Initialise the SQLAlchemy engine for the verify database."""
    global _engine  # noqa: PLW0603
    url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"
    _engine = create_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    logger.info("Verify DB engine initialised (host=%s, db=%s)", host, db_name)


def get_engine() -> Engine | None:
    """Return the current engine, or None if not initialised."""
    return _engine


def _read_extra_info(conn, job_uuid: str) -> dict | None:
    """Read and parse extra_info for a job. Returns None if job not found."""
    row = conn.execute(
        text("SELECT extra_info FROM evaluation_jobs WHERE obj_uuid = :uuid"),
        {"uuid": job_uuid},
    ).fetchone()

    if not row:
        return None

    raw_extra = row[0]
    if raw_extra is None:
        return {}
    if isinstance(raw_extra, str):
        return json.loads(raw_extra)
    return dict(raw_extra)


async def store_chat_id(
    job_uuid: str,
    chat_id: int = 0,
    whatsapp_phone: str = "",
) -> bool:
    """Store notification identifiers in the extra_info JSON field.

    Supports both Telegram (chat_id) and WhatsApp (phone number).
    Reads current extra_info, merges the identifier(s), and writes back.
    Returns True on success, False on failure.
    """
    if not _engine:
        logger.warning("DB not configured, cannot store identifiers for job %s", job_uuid)
        return False

    try:
        with _engine.connect() as conn:
            extra_info = _read_extra_info(conn, job_uuid)
            if extra_info is None:
                logger.warning("Job %s not found in DB", job_uuid)
                return False

            if chat_id:
                extra_info["telegram_chat_id"] = chat_id
            if whatsapp_phone:
                extra_info["whatsapp_phone"] = whatsapp_phone

            conn.execute(
                text("UPDATE evaluation_jobs SET extra_info = :extra WHERE obj_uuid = :uuid"),
                {"extra": json.dumps(extra_info), "uuid": job_uuid},
            )
            conn.commit()
            logger.info(
                "Stored notification info for job %s (tg=%s, wa=%s)",
                job_uuid, chat_id or "-", whatsapp_phone or "-",
            )
            return True
    except Exception:
        logger.exception("Failed to store identifiers for job %s", job_uuid)
        return False


@dataclass
class NotificationTarget:
    """Holds notification targets retrieved from extra_info."""

    telegram_chat_id: int | None = None
    whatsapp_phone: str | None = None


async def get_notification_target(job_uuid: str) -> NotificationTarget:
    """Retrieve notification targets from the extra_info JSON field.

    Returns a NotificationTarget with whichever identifiers are stored.
    """
    if not _engine:
        logger.warning("DB not configured, cannot get notification target for job %s", job_uuid)
        return NotificationTarget()

    try:
        with _engine.connect() as conn:
            extra_info = _read_extra_info(conn, job_uuid)
            if extra_info is None:
                return NotificationTarget()

            tg_id = extra_info.get("telegram_chat_id")
            wa_phone = extra_info.get("whatsapp_phone")

            return NotificationTarget(
                telegram_chat_id=int(tg_id) if tg_id is not None else None,
                whatsapp_phone=str(wa_phone) if wa_phone else None,
            )
    except Exception:
        logger.exception("Failed to get notification target for job %s", job_uuid)
        return NotificationTarget()


async def get_chat_id(job_uuid: str) -> int | None:
    """Retrieve telegram_chat_id from extra_info. Convenience wrapper."""
    target = await get_notification_target(job_uuid)
    return target.telegram_chat_id
