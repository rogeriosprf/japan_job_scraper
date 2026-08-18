# site/pages/1_Vagas.py
from datetime import datetime, timezone

import streamlit as st

from auth import check_password
from db import get_jobs, count_jobs_by_status, update_job_status

st.set_page_config(page_title="Vagas", page_icon="📋", layout="centered")

check_password()

st.title("📋 Vagas")

PAGE_SIZE = 20

# Se uma vaga não aparece em nenhuma raspagem há mais que isso, mostramos
# um aviso — o cron roda 6x/dia, 48h dá margem pra falha temporária de
# rede sem virar falso alarme, mas ainda pega vaga que saiu do ar mesmo.
STALE_AFTER_HOURS = 48

STATUS_LABELS = {
    "available": "Disponíveis",
    "applied": "Candidatei-me",
    "discarded": "Descartei",
}


def format_salary(min_v, max_v, currency):
    if not min_v and not max_v:
        return "Salário não informado"

    def fmt(v):
        if not v:
            return "?"
        return f"{currency} {v / 1_000_000:.1f}M" if v >= 1_000_000 else f"{currency} {v:,.0f}"

    if min_v and max_v:
        return f"{fmt(min_v)} - {fmt(max_v)} / ano"
    return f"{fmt(min_v or max_v)} / ano"


def format_visa(v):
    if v is True:
        return "✅ Sponsor"
    elif v is False:
        return "⚠️ Provavelmente não"
    return "❔ Não informado"


def render_tab(status_key: str):
    page_key = f"page_{status_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total = count_jobs_by_status(status_key)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = st.session_state[page_key]

    st.caption(f"{total} vagas — página {page + 1} de {total_pages}")

    jobs = get_jobs(status_key, limit=PAGE_SIZE, offset=page * PAGE_SIZE)

    if not jobs:
        st.info("Nenhuma vaga aqui.")
        return

    for job in jobs:
        with st.container(border=True):
            st.markdown(f"**{job['title']}**")
            st.caption(f"{job['company']} — {job['source']}")

            last_seen = job.get("last_seen_at")
            if last_seen:
                hours_since = (datetime.now(timezone.utc) - last_seen).total_seconds() / 3600
                if hours_since > STALE_AFTER_HOURS:
                    st.warning(f"⚠️ Não confirmada há {int(hours_since // 24)} dia(s) — pode estar fora do ar.")

            st.write(format_salary(job["salary_min"], job["salary_max"], job["salary_currency"]))
            st.write(f"🛂 {format_visa(job['visa_sponsorship'])} · 🗣️ {job['japanese_level'] or 'Não informado'}")
            st.write(f"📊 Score: {job['match_score']}")

            techs = job.get("technologies") or []
            if techs:
                st.caption(", ".join(techs[:8]))

            if job["application_url"]:
                st.link_button("Ver vaga", job["application_url"])

            # Botões de ação empilhados (não lado a lado) — mais seguro
            # em tela estreita de celular do que colunas apertadas.
            if status_key == "available":
                if st.button("✅ Candidatar-me", key=f"apply_{job['job_key']}", use_container_width=True):
                    update_job_status(job["job_key"], "applied")
                    st.rerun()
                if st.button("🗑️ Descartar", key=f"discard_{job['job_key']}", use_container_width=True):
                    update_job_status(job["job_key"], "discarded")
                    st.rerun()
            elif status_key == "applied":
                if st.button("↩️ Voltar pra disponíveis", key=f"revert_{job['job_key']}", use_container_width=True):
                    update_job_status(job["job_key"], "available")
                    st.rerun()
            elif status_key == "discarded":
                if st.button("↩️ Voltar pra disponíveis", key=f"restore_{job['job_key']}", use_container_width=True):
                    update_job_status(job["job_key"], "available")
                    st.rerun()

    col_prev, col_next = st.columns(2)
    if col_prev.button("← Anterior", disabled=(page == 0), key=f"prev_{status_key}", use_container_width=True):
        st.session_state[page_key] -= 1
        st.rerun()
    if col_next.button("Próxima →", disabled=(page >= total_pages - 1), key=f"next_{status_key}", use_container_width=True):
        st.session_state[page_key] += 1
        st.rerun()


tab_available, tab_applied, tab_discarded = st.tabs(list(STATUS_LABELS.values()))

with tab_available:
    render_tab("available")

with tab_applied:
    render_tab("applied")

with tab_discarded:
    render_tab("discarded")