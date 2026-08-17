import json
import os
import re
import time
import httpx
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Any, Optional

# Slugs estruturais conhecidos (catalogados a partir do HTML real do site).
# Qualquer tag /jobs/<slug> que não esteja nesses conjuntos é tratada como stack.
JAPANESE_TAG = "japanese-required"
NO_JAPANESE_TAG = "no-japanese-required"
REMOTE_TAGS = {"fully-remote", "partially-remote", "no-remote"}
RESIDENCY_TAGS = {"apply-from-abroad", "residents-only"}
SALARY_TAG = "salary-data"


def parse_salary(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Converte strings como '¥6.4M ~ ¥11.0M' para o objeto estruturado de salário."""
    if not text or "¥" not in text:
        return None

    matches = re.findall(r"¥?\s*([\d\.]+)\s*([MKk]?)", text)
    if not matches:
        return None

    values = []
    for val, multiplier in matches:
        try:
            num = float(val)
            if multiplier.upper() == 'M':
                num *= 1_000_000
            elif multiplier.upper() == 'K':
                num *= 1_000
            values.append(int(num))
        except ValueError:
            continue

    if not values:
        return None

    return {
        "min": min(values),
        "max": max(values) if len(values) > 1 else min(values),
        "currency": "JPY",
        "text": text.strip()
    }


def classify_tags(card: Optional[Tag]):
    """
    Lê todas as tags /jobs/<slug> dentro do card da vaga e separa em:
    - salary_text, japanese_level, remote_policy, applicant_location (metadados estruturais)
    - stack (tudo que sobrar: linguagens e categorias como SRE, DevOps, AWS, etc.)

    Isso substitui a abordagem antiga de keyword-guessing em texto livre por
    leitura exata dos mesmos slugs que o próprio site usa nos filtros dele.
    """
    salary_text = None
    japanese_level = None
    remote_policy = None
    applicant_location = None
    stack = []

    if card and isinstance(card, Tag):
        for tag_elem in card.select("a[href^='/jobs/']"):
            href = tag_elem.get("href", "").strip("/")
            slug = href.split("/")[-1] if href.startswith("jobs/") else href
            text = tag_elem.get_text(strip=True)

            if slug == SALARY_TAG:
                salary_text = text
            elif slug == JAPANESE_TAG:
                japanese_level = text  # "Basic/Business/Fluent/Conversational Japanese"
            elif slug == NO_JAPANESE_TAG:
                japanese_level = "No Japanese required"
            elif slug in REMOTE_TAGS:
                remote_policy = text
            elif slug in RESIDENCY_TAGS:
                applicant_location = text
            else:
                stack.append(text)

    return salary_text, japanese_level, remote_policy, applicant_location, sorted(set(stack))


def fetch_raw_tokyodev() -> List[Dict[str, Any]]:
    os.makedirs("data", exist_ok=True)

    url = "https://www.tokyodev.com/jobs"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
    if response.status_code != 200:
        print(f"[TokyoDev] Erro HTTP {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    raw_jobs = []
    seen_urls = set()

    links_vagas = soup.select("a[href*='/companies/'][href*='/jobs/']")

    for anchor in links_vagas:
        href = anchor.get("href", "").split("?")[0].rstrip("/")
        if not href or href in seen_urls:
            continue

        full_url = f"https://www.tokyodev.com{href}" if not href.startswith("http") else href
        seen_urls.add(href)

        path_parts = href.strip("/").split("/")
        if len(path_parts) < 4 or path_parts[0] != "companies" or path_parts[2] != "jobs":
            continue

        company_slug = path_parts[1].replace("-", " ").title()
        raw_id = path_parts[-1]
        title = anchor.get_text(strip=True)

        if not title:
            continue

        # Container da VAGA individual, não o <li> da empresa inteira.
        # Quando uma empresa tem várias vagas abertas, elas ficam agrupadas
        # no mesmo <li> — pegar o <li> inteiro mistura stack/salário/tags
        # de vagas diferentes da mesma empresa.
        card = (
            anchor.find_parent("div", attrs={"data-collapsable-list-target": "item"})
            or anchor.find_parent("li")
            or anchor.find_parent("div", class_=lambda c: c and "job" in c)
            or anchor.parent
        )

        salary_text, japanese_level, remote_policy, applicant_location, stack = classify_tags(card)

        raw_jobs.append({
            # Chave composta (empresa + slug) evita colisão entre vagas de
            # empresas diferentes que reusam o mesmo raw_id (ex: "backend-engineer").
            "job_key": f"{path_parts[1]}/{raw_id}",
            "raw_id": raw_id,
            "title": title,
            "company": company_slug,
            "url": full_url,
            "source": "TokyoDev",
            "salary": parse_salary(salary_text),
            "japanese_level": japanese_level,
            "remote_policy": remote_policy,
            "applicant_location": applicant_location,
            "stack": stack,
            "visa_sponsorship": None,  # só disponível depois do enrich_with_details (fase 2)
            "raw_payload": str(card) if card else str(anchor),
        })

    json_path = "data/raw_tokyodev.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_jobs, f, ensure_ascii=False, indent=2)

    print(f"[TokyoDev] Processamento concluído: {len(raw_jobs)} vagas estruturadas salvas em {json_path}")
    return raw_jobs


# --------------------------------------------------------------------------
# Fase 2: detalhe da vaga — captura o sinal "Relocate to Japan" que só
# aparece na página de detalhe, dentro do bloco de quick-facts com emoji
# (<li><span class="emoji">🌏</span>...Apply from abroad / Relocate to
# Japan...</li>). O site não expõe nenhum campo estruturado de "sponsor"
# (confirmado por busca no HTML inteiro), então usamos esse proxy: vaga
# exige mudança pro Japão + aceita candidatura do exterior => a empresa
# precisa viabilizar o visto para isso acontecer.
# --------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def fetch_job_detail(url: str) -> Optional[Dict[str, Any]]:
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[TokyoDev] Erro ao buscar detalhe {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    visa_sponsorship = None

    # Acha o <li> do bloco de quick-facts que contém o emoji 🌏
    # (apply from abroad / relocate to japan).
    for emoji_span in soup.select("span.emoji"):
        if emoji_span.get_text(strip=True) == "🌏":
            li = emoji_span.find_parent("li")
            if li:
                block_text = li.get_text(separator=" ", strip=True).lower()
                if "relocate to japan" in block_text:
                    visa_sponsorship = True
            break

    return {
        "visa_sponsorship": visa_sponsorship,
    }


def enrich_with_details(jobs: List[Dict[str, Any]], matcher=None, delay: float = 2.0) -> List[Dict[str, Any]]:
    """
    Busca o detalhe de cada vaga pra capturar visa_sponsorship. Se um
    JobMatcher for passado, aplica should_fetch_details (só título) antes
    de gastar o request — mesmo padrão do CareerCross. Vagas já
    processadas (visa_sponsorship != None) são puladas, pra permitir
    retomar uma execução interrompida.
    """
    fetched, skipped_by_filter, skipped_already_done = 0, 0, 0

    for job in jobs:
        if job.get("visa_sponsorship") is not None:
            skipped_already_done += 1
            continue

        if matcher is not None and not matcher.should_fetch_details(job):
            skipped_by_filter += 1
            continue

        detail = fetch_job_detail(job["url"])
        if detail:
            job["visa_sponsorship"] = detail["visa_sponsorship"]
            fetched += 1

        time.sleep(delay)

    print(
        f"[TokyoDev] Detalhe: {fetched} buscadas | {skipped_by_filter} puladas pelo filtro | "
        f"{skipped_already_done} já processadas antes"
    )
    return jobs


if __name__ == "__main__":
    fetch_raw_tokyodev()