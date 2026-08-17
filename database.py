# database.py
import os
import logging
from typing import List, Dict, Any, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Connection string do Supabase: Project Settings > Database > Connection string
# (formato: postgresql://postgres:[password]@[host]:5432/postgres)
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada (variável de ambiente ausente).")
    return psycopg2.connect(DATABASE_URL)


def _flatten_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Achata o Job pydantic (company/location/salary/requirements aninhados,
    como vem de jobs_latest.json + matcher.rank_jobs) pro formato de
    colunas do Postgres.
    """
    company = job.get("company") or {}
    location = job.get("location") or {}
    salary = job.get("salary") or {}
    requirements = job.get("requirements") or {}

    return {
        "job_key": job["job_key"],
        "source": job.get("source"),
        "title": job.get("title"),
        "company": company.get("name") if isinstance(company, dict) else company,
        "location_city": location.get("city") if isinstance(location, dict) else location,
        "location_country": (location.get("country") if isinstance(location, dict) else None) or "Japan",
        "remote_policy": location.get("remote_policy") if isinstance(location, dict) else None,
        "salary_min": salary.get("min") if isinstance(salary, dict) else None,
        "salary_max": salary.get("max") if isinstance(salary, dict) else None,
        "salary_currency": (salary.get("currency") if isinstance(salary, dict) else None) or "JPY",
        "employment_type": job.get("employment_type"),
        "japanese_level": requirements.get("japanese_level") if isinstance(requirements, dict) else None,
        "english_level": requirements.get("english_level") if isinstance(requirements, dict) else None,
        "seniority": requirements.get("seniority") if isinstance(requirements, dict) else None,
        "visa_sponsorship": job.get("visa_sponsorship"),
        "description": job.get("description"),
        "application_url": job.get("application_url"),
        "technologies": psycopg2.extras.Json(job.get("skills") or []),
        "match_score": job.get("fit_score", job.get("match_score")),
        "score_reasons": psycopg2.extras.Json(job.get("score_reasons") or []),
        "published_at": job.get("published_at"),
    }


def upsert_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Insere/atualiza vagas por job_key. Em conflito (vaga já existe),
    atualiza os dados da vaga mas PRESERVA status/status_updated_at —
    nunca sobrescreve o que o usuário marcou manualmente no site.
    Retorna a lista de vagas genuinamente novas (job dicts achatados),
    pra notificação.
    """
    if not jobs:
        return []

    conn = get_connection()
    new_jobs: List[Dict[str, Any]] = []

    try:
        with conn:
            with conn.cursor() as cur:
                for job in jobs:
                    flat = _flatten_job(job)

                    cur.execute("SELECT 1 FROM jobs WHERE job_key = %s", (flat["job_key"],))
                    exists = cur.fetchone()

                    if exists:
                        cur.execute("""
                            UPDATE jobs SET
                                title = %(title)s,
                                company = %(company)s,
                                location_city = %(location_city)s,
                                location_country = %(location_country)s,
                                remote_policy = %(remote_policy)s,
                                salary_min = %(salary_min)s,
                                salary_max = %(salary_max)s,
                                salary_currency = %(salary_currency)s,
                                employment_type = %(employment_type)s,
                                japanese_level = %(japanese_level)s,
                                english_level = %(english_level)s,
                                seniority = %(seniority)s,
                                visa_sponsorship = %(visa_sponsorship)s,
                                description = %(description)s,
                                application_url = %(application_url)s,
                                technologies = %(technologies)s,
                                match_score = %(match_score)s,
                                score_reasons = %(score_reasons)s,
                                published_at = %(published_at)s,
                                last_seen_at = now()
                            WHERE job_key = %(job_key)s
                        """, flat)
                    else:
                        cur.execute("""
                            INSERT INTO jobs (
                                job_key, source, title, company,
                                location_city, location_country, remote_policy,
                                salary_min, salary_max, salary_currency,
                                employment_type, japanese_level, english_level, seniority,
                                visa_sponsorship, description, application_url, technologies,
                                match_score, score_reasons, published_at
                            ) VALUES (
                                %(job_key)s, %(source)s, %(title)s, %(company)s,
                                %(location_city)s, %(location_country)s, %(remote_policy)s,
                                %(salary_min)s, %(salary_max)s, %(salary_currency)s,
                                %(employment_type)s, %(japanese_level)s, %(english_level)s, %(seniority)s,
                                %(visa_sponsorship)s, %(description)s, %(application_url)s, %(technologies)s,
                                %(match_score)s, %(score_reasons)s, %(published_at)s
                            )
                        """, flat)
                        # devolve a versão "plana" — é o formato que o
                        # TelegramNotifier espera (job.get("salary_min") etc.)
                        new_job = dict(flat)
                        new_job["technologies"] = job.get("skills") or []
                        new_job["score_reasons"] = job.get("score_reasons") or []
                        new_jobs.append(new_job)
    finally:
        conn.close()

    return new_jobs


def count_jobs() -> int:
    """Usado pra decidir se essa é a carga inicial (banco vazio antes do upsert)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            return cur.fetchone()[0]
    finally:
        conn.close()


def mark_notified(job_keys: List[str]):
    if not job_keys:
        return
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET notified_at = now() WHERE job_key = ANY(%s)",
                    (job_keys,)
                )
    finally:
        conn.close()


def mark_all_notified():
    """Usado na carga inicial: marca tudo como notificado (o resumo já
    cobriu essas vagas), pra próxima rodada não tentar notificar de novo."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE jobs SET notified_at = now() WHERE notified_at IS NULL")
    finally:
        conn.close()


def get_matcher_profile() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT core_skills, secondary_skills, roles, avoid, seniority, language
                FROM matcher_profile WHERE id = 1
            """)
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def log_scrape_run(source: str, jobs_found: int, new_jobs: int, status: str = "success", error_message: Optional[str] = None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scrape_runs (source, jobs_found, new_jobs, status, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                """, (source, jobs_found, new_jobs, status, error_message))
    finally:
        conn.close()