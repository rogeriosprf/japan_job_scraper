# site/pages/1_Vagas.py
from datetime import datetime, timezone

import streamlit as st

from auth import check_password
from db import get_jobs, count_jobs_by_status, update_job_status

st.set_page_config(page_title="Vagas", page_icon="📋", layout="centered")

check_password()

# CSS mínimo — só estilo, zero JavaScript. Dá cor e hierarquia aos cards
# sem sair do modelo do Streamlit (nenhum componente interativo daqui).
st.markdown("""
<style>
.job-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 0.1rem; line-height: 1.3; }
.job-subtitle { color: #6b7280; font-size: 0.85rem; margin-bottom: 0.5rem; }
.badge-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 0.4rem 0; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; white-space: nowrap; }
.badge-score-high { background: #dcfce7; color: #166534; }
.badge-score-mid { background: #dbeafe; color: #1e40af; }
.badge-score-low { background: #f3f4f6; color: #4b5563; }
.badge-score-neg { background: #fee2e2; color: #991b1b; }
.badge-visa-yes { background: #dcfce7; color: #166534; }
.badge-visa-no { background: #fef3c7; color: #92400e; }
.badge-visa-unknown { background: #f3f4f6; color: #6b7280; }
.badge-neutral { background: #f3f4f6; color: #374151; }
.job-salary { font-size: 0.95rem; font-weight: 600; color: #111827; margin: 0.3rem 0; }
.job-tech { color: #6b7280; font-size: 0.8rem; margin-top: 0.3rem; }
</style>
""", unsafe_allow_html=True)

st.title("📋 Vagas")

PAGE_SIZE = 20

# Se uma vaga não aparece em nenhuma raspagem há mais que isso, mostramos
# um aviso — o cron roda 6x/dia, 48h dá margem pra falha temporária de
# rede sem virar falso alarme, mas ainda pega vaga que saiu do ar mesmo.
# Obs: não pega vaga que a fonte mantém no índice de busca mesmo depois
# de fechada (ex: possível atraso da Algolia no JapanDev) — limitação
# conhecida, não tem como resolver só com esse sinal.
STALE_AFTER_HOURS = 48

STATUS_LABELS = {
    "available": "Disponíveis",
    "applied": "Candidatei-me",
    "discarded": "Descartei",
}

SORT_OPTIONS = {
    "Melhor match": "score",
    "Mais recentes": "recent",
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


def score_badge(score):
    score = score or 0
    if score < 0:
        cls, label = "badge-score-neg", f"📉 {score:.0f} pts"
    elif score < 50:
        cls, label = "badge-score-low", f"📊 {score:.0f} pts"
    elif score < 150:
        cls, label = "badge-score-mid", f"📊 {score:.0f} pts"
    else:
        cls, label = "badge-score-high", f"🔥 {score:.0f} pts"
    return f'<span class="badge {cls}">{label}</span>'


def visa_badge(v):
    if v is True:
        return '<span class="badge badge-visa-yes">✅ Sponsor</span>'
    elif v is False:
        return '<span class="badge badge-visa-no">⚠️ Provável não</span>'
    return '<span class="badge badge-visa-unknown">❔ Visto não informado</span>'


def neutral_badge(text):
    return f'<span class="badge badge-neutral">{text}</span>'


def render_tab(status_key: str, sort_key: str):
    page_key = f"page_{status_key}_{sort_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total = count_jobs_by_status(status_key)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = st.session_state[page_key]

    st.caption(f"{total} vagas — página {page + 1} de {total_pages}")

    jobs = get_jobs(status_key, limit=PAGE_SIZE, offset=page * PAGE_SIZE, order_by=sort_key)

    if not jobs:
        st.info("Nenhuma vaga aqui.")
        return

    for job in jobs:
        with st.container(border=True):
            last_seen = job.get("last_seen_at")
            if last_seen:
                hours_since = (datetime.now(timezone.utc) - last_seen).total_seconds() / 3600
                if hours_since > STALE_AFTER_HOURS:
                    st.warning(f"⚠️ Não confirmada há {int(hours_since // 24)} dia(s) — pode estar fora do ar.")

            techs = job.get("technologies") or []
            tech_line = ", ".join(techs[:8]) if techs else ""

            card_html = f"""
            <div class="job-title">{job['title']}</div>
            <div class="job-subtitle">{job['company']} — {job['source']}</div>
            <div class="badge-row">
                {score_badge(job['match_score'])}
                {visa_badge(job['visa_sponsorship'])}
                {neutral_badge(job['japanese_level'] or 'Japonês não informado')}
            </div>
            <div class="job-salary">💵 {format_salary(job['salary_min'], job['salary_max'], job['salary_currency'])}</div>
            {f'<div class="job-tech">🛠️ {tech_line}</div>' if tech_line else ''}
            """
            st.markdown(card_html, unsafe_allow_html=True)

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
    if col_prev.button("← Anterior", disabled=(page == 0), key=f"prev_{status_key}_{sort_key}", use_container_width=True):
        st.session_state[page_key] -= 1
        st.rerun()
    if col_next.button("Próxima →", disabled=(page >= total_pages - 1), key=f"next_{status_key}_{sort_key}", use_container_width=True):
        st.session_state[page_key] += 1
        st.rerun()


sort_label = st.radio("Ordenar por", list(SORT_OPTIONS.keys()), horizontal=True)
sort_key = SORT_OPTIONS[sort_label]

tab_available, tab_applied, tab_discarded = st.tabs(list(STATUS_LABELS.values()))

with tab_available:
    render_tab("available", sort_key)

with tab_applied:
    render_tab("applied", sort_key)

with tab_discarded:
    render_tab("discarded", sort_key)