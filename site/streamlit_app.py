# site/streamlit_app.py
import streamlit as st

from auth import check_password
from db import get_stats

st.set_page_config(page_title="Japan Job Tracker", page_icon="🇯🇵", layout="centered")

check_password()

st.title("🇯🇵 Japan Job Tracker")

totals, by_source, recent_runs = get_stats()

col1, col2, col3 = st.columns(3)
col1.metric("Disponíveis", totals["available"])
col2.metric("Candidatei-me", totals["applied"])
col3.metric("Descartei", totals["discarded"])

st.metric("Novas nas últimas 24h", totals["new_last_24h"])

st.divider()

st.subheader("Por fonte")
for row in by_source:
    st.write(f"**{row['source']}**: {row['total']} vagas")

st.divider()

st.subheader("Últimas execuções do scraper")
if not recent_runs:
    st.caption("Nenhuma execução registrada ainda.")
for run in recent_runs:
    icon = "✅" if run["status"] == "success" else "❌"
    st.write(f"{icon} **{run['source']}** — {run['jobs_found']} vagas encontradas — {run['ran_at']}")

st.divider()

st.page_link("pages/1_Vagas.py", label="Ver vagas →", icon="📋")
