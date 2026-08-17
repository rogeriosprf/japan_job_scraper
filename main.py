# main.py
#
# Orquestração geral, pensada pra rodar via GitHub Actions a cada 3h:
#
#   1. Scrape (JapanDev + TokyoDev + CareerCross)
#   2. Enrich seletivo de detalhe — só pras vagas que ainda NÃO existem
#      no Postgres (evita re-bater nos sites a cada rodada pra vaga já
#      enriquecida antes)
#   3. Normalize (junta as 3 fontes no formato Job)
#   4. Match (score com o profile vindo do Supabase)
#   5. Upsert no Postgres por job_key — preserva status/status_updated_at
#   6. Notificação Telegram:
#      - banco vazio antes do upsert => carga inicial => 1 mensagem resumo
#      - senão => 1 mensagem por vaga nova
#   7. Log da rodada em scrape_runs

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Carrega .env se existir — não sobrescreve variáveis já exportadas no
# shell/CI (no GitHub Actions, os secrets já vêm como env vars reais,
# então isso é essencialmente um no-op lá; é pro caso de rodar local).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database as db
from transformers.matcher import JobMatcher
from transformers.normalize import main as run_normalize
from notifiers.telegram import TelegramNotifier

from scrapers.japan_dev import JapanDevScraper
from scrapers.tokyo_dev import fetch_raw_tokyodev, enrich_with_details as enrich_tokyodev_details
from scrapers.careercross import CareerCrossScraper


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NORMALIZED_JSON = Path("data/normalized/jobs_latest.json")
CAREERCROSS_JSON = Path("data/raw/careercross.json")
TOKYODEV_JSON = Path("data/raw/tokyo_dev.json")


def load_existing_keys() -> set:
    """job_keys que já existem no Postgres — usado pra decidir quais
    vagas raspadas agora precisam de fetch de detalhe (só as novas)."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT job_key FROM jobs")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def run_scrapers(matcher: JobMatcher, existing_keys: set):
    """Roda os 3 scrapers. CareerCross e TokyoDev só buscam detalhe das
    vagas que ainda não estão no Postgres — a listagem inteira é sempre
    re-raspada (é rápida), mas o enrich caro só roda pro que é novo."""

    results = {}

    # --- JapanDev (Algolia, já vem completo, sem fase de detalhe) ---
    try:
        jd_jobs = JapanDevScraper().fetch_jobs()
        results["JapanDev"] = {"found": len(jd_jobs), "error": None}
    except Exception as e:
        logger.exception("Erro no JapanDev")
        results["JapanDev"] = {"found": 0, "error": str(e)}

    # --- TokyoDev ---
    try:
        td_jobs = fetch_raw_tokyodev()

        # só gasta request de detalhe em vaga genuinamente nova
        pending = [j for j in td_jobs if j["job_key"] not in existing_keys]
        if pending:
            enrich_tokyodev_details(pending, matcher=matcher, delay=2.0)

        with open(TOKYODEV_JSON, "w", encoding="utf-8") as f:
            json.dump(td_jobs, f, ensure_ascii=False, indent=2)

        results["TokyoDev"] = {"found": len(td_jobs), "error": None}
    except Exception as e:
        logger.exception("Erro no TokyoDev")
        results["TokyoDev"] = {"found": 0, "error": str(e)}

    # --- CareerCross ---
    try:
        cc_scraper = CareerCrossScraper(delay=2.5)
        cc_jobs = cc_scraper.fetch_jobs()  # listagem completa (rápida)

        pending = [j for j in cc_jobs if j["job_key"] not in existing_keys]
        if pending:
            cc_scraper.enrich_with_details(pending, matcher=matcher)

        with open(CAREERCROSS_JSON, "w", encoding="utf-8") as f:
            json.dump(cc_jobs, f, ensure_ascii=False, indent=2)

        results["CareerCross"] = {"found": len(cc_jobs), "error": None}
    except Exception as e:
        logger.exception("Erro no CareerCross")
        results["CareerCross"] = {"found": 0, "error": str(e)}

    return results


def main():
    logger.info("=== Iniciando rodada ===")

    # profile do Supabase — se falhar, cai pro profile.py estático
    # (fallback silencioso pra não travar a rodada inteira por causa disso)
    try:
        profile = db.get_matcher_profile()
        if profile:
            logger.info("Profile carregado do Supabase.")
        else:
            logger.warning("matcher_profile vazio no Supabase, usando config/profile.py.")
    except Exception:
        logger.exception("Falha ao ler matcher_profile do Supabase, usando config/profile.py.")
        profile = None

    matcher = JobMatcher(profile=profile)

    # é carga inicial? (checa ANTES do upsert)
    try:
        is_first_load = db.count_jobs() == 0
    except Exception:
        logger.exception("Falha ao checar contagem inicial do Postgres — abortando rodada.")
        return

    existing_keys = load_existing_keys()

    scrape_results = run_scrapers(matcher, existing_keys)

    for source, result in scrape_results.items():
        db.log_scrape_run(
            source=source,
            jobs_found=result["found"],
            new_jobs=0,  # atualizado depois do upsert, abaixo
            status="error" if result["error"] else "success",
            error_message=result["error"],
        )

    # normaliza as 3 fontes num JSON só (Job schema)
    run_normalize()

    with open(NORMALIZED_JSON, encoding="utf-8") as f:
        jobs = json.load(f)

    ranked = matcher.rank_jobs(jobs).to_dicts()

    new_jobs = db.upsert_jobs(ranked)

    logger.info(f"Upsert concluído: {len(ranked)} processadas, {len(new_jobs)} novas.")

    notifier = TelegramNotifier()

    if is_first_load:
        notifier.send_summary(new_jobs)
        db.mark_all_notified()
    else:
        sent_keys = notifier.send_new_jobs(new_jobs)
        db.mark_notified(sent_keys)

    logger.info("=== Rodada concluída ===")


if __name__ == "__main__":
    main()