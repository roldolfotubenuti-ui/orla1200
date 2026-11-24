"""Daily scheduler rule engine for TKS Engine 3.0.

Horários e limites oficiais por dia da semana (fuso de Brasília - America/Sao_Paulo):
- Máximo 5 vídeos por conta por dia.
- SEGUNDA-FEIRA: 08:00, 11:00, 13:00, 19:00, 20:30
- TERÇA-FEIRA:   07:00, 10:00, 16:00, 19:00, 20:30
- QUARTA-FEIRA:  09:00, 12:00, 18:00, 19:30, 20:30
- QUINTA-FEIRA:  09:00, 13:00, 17:00, 19:00, 20:30
- SEXTA-FEIRA:   08:00, 11:00, 16:00, 18:00, 20:00
- SÁBADO:        09:00, 12:00, 16:00, 17:00, 20:00
- DOMINGO:       09:00, 12:00, 13:00, 18:00, 20:00

Regra de alocação sequencial:
- Começa no dia e horário mais próximos que ainda não foram reservados e que estejam no futuro (+25 min).
- Ao atingir 5 vídeos no dia, salta automaticamente para os horários do dia seguinte.
- Se novos vídeos forem adicionados, o agendamento continua exatamente de onde parou.
"""
from __future__ import annotations

import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import Any

from core.db_manager import DatabaseManager

logger = logging.getLogger("tks.daily_scheduler")

DEFAULT_SCHEDULE_TIMEZONE = "America/Sao_Paulo"
MAX_VIDEOS_PER_DAY = 5
DEFAULT_CAPTION = "meu brasil #fy #foryou"

# Horários oficiais solicitados (fuso de Brasília)
# 0 = Segunda, 1 = Terça, 2 = Quarta, 3 = Quinta, 4 = Sexta, 5 = Sábado, 6 = Domingo
WEEKDAY_SCHEDULE_SLOTS: dict[int, list[str]] = {
    0: ["08:00", "11:00", "13:00", "19:00", "20:30"],  # SEGUNDA-FEIRA
    1: ["07:00", "10:00", "16:00", "19:00", "20:30"],  # TERÇA-FEIRA
    2: ["09:00", "12:00", "18:00", "19:30", "20:30"],  # QUARTA-FEIRA
    3: ["09:00", "13:00", "17:00", "19:00", "20:30"],  # QUINTA-FEIRA
    4: ["08:00", "11:00", "16:00", "18:00", "20:00"],  # SEXTA-FEIRA
    5: ["09:00", "12:00", "16:00", "17:00", "20:00"],  # SÁBADO
    6: ["09:00", "12:00", "13:00", "18:00", "20:00"],  # DOMINGO
}

# Retrocompatibilidade
DEFAULT_SCHEDULE_TIME = "08:00"
VIDEOS_PER_ACCOUNT_PER_DAY = MAX_VIDEOS_PER_DAY


def get_account_booked_slots(
    account_id: str,
    db: DatabaseManager | None = None,
    exclude_job_id: str | None = None,
) -> set[str]:
    """Recupera todos os horários exatos já reservados para esta conta.

    Retorna strings formatadas como 'YYYY-MM-DD HH:MM'.
    """
    db_mgr = db or DatabaseManager.get_instance()
    booked: set[str] = set()

    with db_mgr.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, schedule_time FROM jobs
            WHERE account_id = ?
              AND status IN ('READY_FOR_UPLOAD', 'ASSIGNED', 'RUNNING', 'UPLOADING', 'PROCESSING', 'SUBMITTING', 'SCHEDULED', 'PUBLISHED', 'ARCHIVED')
              AND schedule_time IS NOT NULL
            """,
            (account_id,),
        )
        for row in cursor.fetchall():
            if exclude_job_id and str(row["id"]) == str(exclude_job_id):
                continue
            raw = str(row["schedule_time"]).strip()
            if len(raw) >= 16:
                booked.add(raw[:16])

    return booked


def get_account_day_counts(
    account_id: str,
    db: DatabaseManager | None = None,
    exclude_job_id: str | None = None,
) -> dict[str, int]:
    """Retorna a contagem de vídeos reservados por data ('YYYY-MM-DD') para esta conta."""
    db_mgr = db or DatabaseManager.get_instance()
    counts: dict[str, int] = {}

    with db_mgr.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, schedule_time FROM jobs
            WHERE account_id = ?
              AND status IN ('READY_FOR_UPLOAD', 'ASSIGNED', 'RUNNING', 'UPLOADING', 'PROCESSING', 'SUBMITTING', 'SCHEDULED', 'PUBLISHED', 'ARCHIVED')
              AND schedule_time IS NOT NULL
            """,
            (account_id,),
        )
        for row in cursor.fetchall():
            if exclude_job_id and str(row["id"]) == str(exclude_job_id):
                continue
            raw = str(row["schedule_time"]).strip()
            date_part = raw.split(" ")[0]
            if len(date_part) == 10 and date_part.count("-") == 2:
                counts[date_part] = counts.get(date_part, 0) + 1

    return counts


def get_account_booked_dates(account_id: str, db: DatabaseManager | None = None) -> set[str]:
    """Retorna as datas ('YYYY-MM-DD') que já atingiram o limite máximo diário de 5 vídeos."""
    counts = get_account_day_counts(account_id, db=db)
    return {d for d, c in counts.items() if c >= MAX_VIDEOS_PER_DAY}


def calculate_next_daily_slot(
    account_id: str,
    db: DatabaseManager | None = None,
    target_time: str | None = None,
    tz_name: str = DEFAULT_SCHEDULE_TIMEZONE,
    exclude_job_id: str | None = None,
) -> tuple[datetime, str]:
    """Calcula o próximo dia e horário vago para a conta, respeitando a tabela de horários e 5 vídeos/dia.

    :return: (datetime_object, formatted_string_YYYY_MM_DD_HH_MM_SS)
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")

    now = datetime.now(tz)
    booked_slots = get_account_booked_slots(account_id, db=db, exclude_job_id=exclude_job_id)
    day_counts = get_account_day_counts(account_id, db=db, exclude_job_id=exclude_job_id)

    candidate_date = now.date()

    # Procurar até 45 dias à frente para acomodar dezenas de vídeos em fila
    for _ in range(45):
        date_str = candidate_date.strftime("%Y-%m-%d")
        current_count = day_counts.get(date_str, 0)

        # Se ainda não atingiu o limite de 5 vídeos neste dia
        if current_count < MAX_VIDEOS_PER_DAY:
            weekday = candidate_date.weekday()
            slots = WEEKDAY_SCHEDULE_SLOTS.get(weekday, ["09:00", "12:00", "16:00", "18:00", "20:00"])

            for slot in slots:
                h_str, m_str = slot.split(":")
                candidate_dt = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    int(h_str),
                    int(m_str),
                    0,
                    tzinfo=tz,
                )

                # Requisito: no mínimo 25 minutos à frente do horário atual de Brasília
                if candidate_dt <= (now + timedelta(minutes=25)):
                    continue

                slot_key = candidate_dt.strftime("%Y-%m-%d %H:%M")
                if slot_key not in booked_slots:
                    formatted = candidate_dt.strftime("%Y-%m-%d %H:%M:%S")
                    return candidate_dt, formatted

        candidate_date += timedelta(days=1)

    # Fallback caso todos os slots nos próximos 45 dias estejam lotados
    fallback_date = now.date() + timedelta(days=1)
    fb_slots = WEEKDAY_SCHEDULE_SLOTS.get(fallback_date.weekday(), ["09:00", "12:00", "16:00", "18:00", "20:00"])
    fb_h, fb_m = fb_slots[0].split(":")
    fallback_dt = datetime(
        fallback_date.year,
        fallback_date.month,
        fallback_date.day,
        int(fb_h),
        int(fb_m),
        0,
        tzinfo=tz,
    )
    return fallback_dt, fallback_dt.strftime("%Y-%m-%d %H:%M:%S")
