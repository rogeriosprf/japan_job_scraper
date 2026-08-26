# site/db.py
import streamlit as st
import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


def get_stats():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                select
                    count(*) filter (where status = 'available') as available,
                    count(*) filter (where status = 'applied') as applied,
                    count(*) filter (where status = 'discarded') as discarded,
                    count(*) as total,
                    count(*) filter (where first_seen_at >= now() - interval '24 hours') as new_last_24h
                from jobs
            """)
            totals = dict(cur.fetchone())

            cur.execute("""
                select source, count(*) as total
                from jobs
                group by source
                order by total desc
            """)
            by_source = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                select source, jobs_found, new_jobs, status, ran_at
                from scrape_runs
                order by ran_at desc
                limit 5
            """)
            recent_runs = [dict(r) for r in cur.fetchall()]

        return totals, by_source, recent_runs
    finally:
        conn.close()


def get_jobs(status: str, limit: int = 20, offset: int = 0, order_by: str = "score"):
    order_clause = {
        "score": "match_score desc nulls last, first_seen_at desc",
        "recent": "first_seen_at desc",
    }.get(order_by, "match_score desc nulls last, first_seen_at desc")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                select job_key, source, title, company, location_city, remote_policy,
                       salary_min, salary_max, salary_currency, employment_type,
                       japanese_level, english_level, visa_sponsorship,
                       application_url, technologies, match_score, first_seen_at,
                       last_seen_at
                from jobs
                where status = %s
                order by {order_clause}
                limit %s offset %s
            """, (status, limit, offset))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def count_jobs_by_status(status: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("select count(*) from jobs where status = %s", (status,))
            return cur.fetchone()[0]
    finally:
        conn.close()

 
def update_job_status(job_key: str, new_status: str):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update jobs set status = %s, status_updated_at = now() where job_key = %s",
                    (new_status, job_key)
                )
    finally:
        conn.close()