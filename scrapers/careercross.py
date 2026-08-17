# scrapers/careercross.py

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CareerCrossScraper:
    """
    Raspa vagas do CareerCross por categoria (evita a busca genérica, que
    mistura todas as áreas). Categorias relevantes para o perfil (dados/
    backend): 8107 = Database Engineer, Architect | 8109 = Software Developer.

    Fluxo por categoria:
      1. GET na URL fixa da categoria (sem sid) -> pega o sid atribuído
         pelo site e o total de vagas.
      2. Usa esse sid para paginar via /job-search/result/{sid}?page=N.

    Vagas patrocinadas (/job-feature/click/XXXX) são ignoradas nesta versão:
    são um link de tracking/redirect, não uma página de detalhe direta.
    """

    BASE_HOST = "https://www.careercross.com"
    HOME_URL = f"{BASE_HOST}/en/"
    CATEGORY_URL = f"{BASE_HOST}/en/job-search/category-{{category_id}}"
    RESULT_URL = f"{BASE_HOST}/en/job-search/result/{{sid}}"

    # category_id -> rótulo legível, só para log/depuração
    CATEGORIES: Dict[str, str] = {
        "8107": "Database Engineer, Architect",
        "8109": "Software Developer",
    }

    RAW_JSON = Path("data/raw/careercross_raw.json")
    OUTPUT_JSON = Path("data/raw/careercross.json")

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.careercross.com/en/job-search",
    }

    def __init__(self, delay: float = 2.0, max_pages_per_category: Optional[int] = None):
        self.session = requests.Session()
        self.delay = delay
        self.max_pages_per_category = max_pages_per_category
        self._warmed_up = False

    # ------------------------------------------------------------------ #
    # Sessão / requests
    # ------------------------------------------------------------------ #

    def _warm_up(self):
        """Visita a home antes de raspar, como um navegador real faria,
        para pegar cookies e reduzir a chance de bloqueio por WAF (403)."""
        if self._warmed_up:
            return
        try:
            self.session.get(self.HOME_URL, headers=self.HEADERS, timeout=20)
        except requests.RequestException as e:
            logger.warning(f"Falha ao aquecer sessão, seguindo mesmo assim: {e}")
        self._warmed_up = True
        time.sleep(1.0)

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        try:
            resp = self.session.get(url, params=params, headers=self.HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar {url} (params={params}): {e}")
            return None

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_sid(html: str) -> Optional[str]:
        m = re.search(r"job-search/result/(\d+)", html)
        return m.group(1) if m else None

    @staticmethod
    def _extract_total(html: str) -> Optional[int]:
        # Tenta os dois formatos observados no site:
        # "Jobs 1 - 20 of 2,213 results" / "2,213 jobs that matched your search criteria."
        m = re.search(r"of\s+([\d,]+)\s+results", html, re.IGNORECASE)
        if not m:
            m = re.search(r"([\d,]+)\s+jobs that matched your search criteria", html, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _table_field(card: Tag, label: str) -> Optional[str]:
        # O site usa <td class="job-box-flex">Label</td> seguido de um <td>
        # de valor cuja classe VARIA (job-box-text na maioria, mas
        # "no-border" no campo Updated) — por isso buscamos pelo <tr> pai
        # e pegamos o segundo <td> por posição, em vez de filtrar por classe.
        label_lower = label.lower()
        for td_label in card.find_all("td", class_="job-box-flex"):
            if label_lower in td_label.get_text(strip=True).lower():
                tr = td_label.find_parent("tr")
                if tr:
                    tds = tr.find_all("td")
                    if len(tds) >= 2:
                        return tds[1].get_text(strip=True)
        return None

    @staticmethod
    def _parse_salary(text: Optional[str]) -> Optional[Dict[str, Any]]:
        """Converte '5 million yen ~ 8.5 million yen' ou
        'Negotiable, based on experience ~ 6 million yen' em min/max."""
        if not text:
            return None

        values = [float(v) for v in re.findall(r"([\d.]+)\s*million yen", text)]
        min_val = int(min(values) * 1_000_000) if values else None
        max_val = int(max(values) * 1_000_000) if values else None

        if min_val is None and max_val is None:
            return {"min": None, "max": None, "currency": "JPY", "text": text.strip()}

        return {
            "min": min_val,
            "max": max_val if len(values) > 1 else min_val,
            "currency": "JPY",
            "text": text.strip(),
        }

    def _parse_cards(self, html: str, category_id: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards_out: List[Dict[str, Any]] = []
        seen_ids = set()

        detail_links = soup.select('a[href*="/job/detail-"]')

        for a in detail_links:
            href = a.get("href", "")
            m = re.search(r"detail-(\d+)", href)
            if not m:
                continue
            job_id = m.group(1)
            if job_id in seen_ids:
                continue

            # Container real do card é <div class="result-job-box">.
            # Usamos isso diretamente agora que confirmamos a estrutura no
            # HTML bruto; mantemos o heurístico antigo (subir até achar uma
            # tabela) como fallback caso o site mude o markup.
            card = a.find_parent("div", class_="result-job-box")
            if card is None:
                card = a.find_parent(["div", "li", "article"])
                hops = 0
                while card is not None and not card.find("table") and hops < 6:
                    card = card.find_parent(["div", "li", "article"])
                    hops += 1
            if card is None:
                continue

            title = a.get_text(strip=True) or "(sem título)"
            company_tag = card.find("a", href=re.compile(r"/company/detail-"))
            company_name = company_tag.get_text(strip=True) if company_tag else None

            location = self._table_field(card, "Location")
            job_type = self._table_field(card, "Job Type")
            salary_text = self._table_field(card, "Salary")
            updated = self._table_field(card, "Updated")

            full_url = href if href.startswith("http") else f"{self.BASE_HOST}{href}"

            cards_out.append({
                "job_key": f"cc-{job_id}",
                "source": "CareerCross",
                "title": title,
                "company": {
                    "name": company_name or "N/A",
                    "slug": None,
                },
                "location": {
                    "city": location,
                    "country": "Japan",
                    "remote_policy": "Remote Work" if "Remote" in title else None,
                    "candidate_location": None,
                },
                "salary": self._parse_salary(salary_text),
                "skills": [],
                "requirements": {
                    "japanese_level": None,   # só disponível na página de detalhe (fase 2)
                    "english_level": None,
                    "seniority": None,
                },
                "employment_type": job_type,
                "visa_sponsorship": None,     # idem — fica para a fase 2
                "job_language": None,
                "active": True,
                "description": None,
                "application_url": full_url.split("?")[0],
                "published_at": updated,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": {
                    "category_id": category_id,
                    "category_label": self.CATEGORIES.get(category_id),
                },
            })
            seen_ids.add(job_id)

        return cards_out

    # ------------------------------------------------------------------ #
    # Orquestração
    # ------------------------------------------------------------------ #

    def _scrape_category(self, category_id: str) -> List[Dict[str, Any]]:
        label = self.CATEGORIES.get(category_id, category_id)
        logger.info(f"Categoria {category_id} ({label})")

        first_page_html = self._get(self.CATEGORY_URL.format(category_id=category_id))
        if not first_page_html:
            logger.error(f"Não foi possível carregar a categoria {category_id}, pulando.")
            return []

        total = self._extract_total(first_page_html)
        sid = self._extract_sid(first_page_html)
        jobs = self._parse_cards(first_page_html, category_id)

        logger.info(f"  Página 1: {len(jobs)} vagas | total reportado pelo site: {total}")

        if not sid:
            logger.warning(f"  Não achei o sid da categoria {category_id}; sem paginação.")
            return jobs

        num_pages = None
        if total:
            num_pages = -(-total // 20)  # ceil division, 20 vagas por página
            if self.max_pages_per_category:
                num_pages = min(num_pages, self.max_pages_per_category)

        page = 2
        while num_pages is None or page <= num_pages:
            time.sleep(self.delay)
            html = self._get(self.RESULT_URL.format(sid=sid), params={"page": page})
            if not html:
                break

            page_jobs = self._parse_cards(html, category_id)
            if not page_jobs:
                logger.info(f"  Página {page}: sem vagas, encerrando categoria.")
                break

            jobs.extend(page_jobs)
            logger.info(f"  Página {page}: {len(page_jobs)} vagas")
            page += 1

            if self.max_pages_per_category and page > self.max_pages_per_category:
                break

        return jobs

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        self._warm_up()

        all_jobs: List[Dict[str, Any]] = []
        seen_keys = set()

        for category_id in self.CATEGORIES:
            category_jobs = self._scrape_category(category_id)
            for job in category_jobs:
                if job["job_key"] in seen_keys:
                    continue
                all_jobs.append(job)
                seen_keys.add(job["job_key"])
            time.sleep(self.delay)

        logger.info(f"Total únicas: {len(all_jobs)}")

        self._save_json(self.RAW_JSON, all_jobs)
        self._save_json(self.OUTPUT_JSON, all_jobs)

        logger.info(f"JSON final criado: {self.OUTPUT_JSON}")
        return all_jobs

    @staticmethod
    def _save_json(path: Path, data: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


    # Termos que indicam patrocínio de visto/COE no texto livre da vaga.
    # visa_status_text (campo estruturado "Visa Status") se mostrou pouco
    # confiável: ~93% das vagas da categoria têm o mesmo texto ("Permission
    # to work in Japan required"), inclusive vagas que citam "VISA
    # Supportあり" na descrição. Por isso escaneamos o texto livre em vez
    # de confiar nesse campo.
    VISA_SUPPORT_KEYWORDS = [
        "visa support", "visa sponsorship", "sponsor visa", "sponsors visa",
        "ビザサポート", "ビザ取得支援", "ビザ発給支援",
        "就労ビザ支援", "在留資格取得支援", "在留資格変更支援",
    ]

    @classmethod
    def _detect_visa_sponsorship(cls, description: Optional[str], required_skills_text: Optional[str]) -> Optional[bool]:
        combined = " ".join(filter(None, [description, required_skills_text])).lower()
        for keyword in cls.VISA_SUPPORT_KEYWORDS:
            if keyword.lower() in combined:
                return True
        # Ausência de menção não significa recusa de patrocínio — fica
        # None (desconhecido) em vez de False, pra não gerar falso-negativo.
        return None

    def fetch_job_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Busca a página de detalhe de uma vaga e extrai description,
        japanese_level, english_level, visa_sponsorship, skills (texto).

        A página de detalhe usa ids únicos por campo (bem mais confiável
        que caçar por texto de label como fizemos na listagem):
        jsonld-description, skill-english-text, skill-japanese-text,
        qualifications-visa-status, qualifications-required-skills.
        """
        html = self._get(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        def by_id(element_id: str) -> Optional[str]:
            el = soup.find(id=element_id)
            return el.get_text(separator="\n", strip=True) if el else None

        description = by_id("jsonld-description")
        english_level = by_id("skill-english-text")
        japanese_level = by_id("skill-japanese-text")
        visa_status_text = by_id("qualifications-visa-status")
        required_skills_text = by_id("qualifications-required-skills")

        # O matcher só lê description/requirements/skills pra montar o
        # texto do score — required_skills_text (a seção "【必須要件】" com
        # a stack técnica exigida) ficava só em raw_payload e nunca entrava
        # nesse texto, fazendo o score ignorar keywords técnicas que só
        # apareciam ali (confirmado em 191/646 vagas). Mesclamos aqui.
        if required_skills_text:
            description = (description or "") + "\n\n【必須要件・required skills】\n" + required_skills_text

        visa_sponsorship = self._detect_visa_sponsorship(description, required_skills_text)

        return {
            "description": description,
            "requirements": {
                "japanese_level": japanese_level,
                "english_level": english_level,
                "seniority": None,
            },
            "visa_sponsorship": visa_sponsorship,
            "visa_status_text": visa_status_text,       # cru, só pra referência/debug
            "required_skills_text": required_skills_text,
        }

    def enrich_with_details(self, jobs: List[Dict[str, Any]], matcher=None) -> List[Dict[str, Any]]:
        """
        Passa cada vaga pelo filtro leve (matcher.should_fetch_details, se
        um JobMatcher for passado) e busca o detalhe só das que passarem.
        Vagas já enriquecidas (description preenchido) são puladas, pra
        permitir retomar uma execução interrompida sem regastar tudo.
        """
        self._warm_up()

        fetched, skipped_by_filter, skipped_already_done = 0, 0, 0

        for job in jobs:
            if job.get("description"):
                skipped_already_done += 1
                continue

            if matcher is not None and not matcher.should_fetch_details(job):
                skipped_by_filter += 1
                continue

            detail = self.fetch_job_detail(job["application_url"])
            if detail:
                job["description"] = detail["description"]
                job["requirements"] = detail["requirements"]
                job["visa_sponsorship"] = detail["visa_sponsorship"]
                job["raw_payload"]["visa_status_text"] = detail["visa_status_text"]
                job["raw_payload"]["required_skills_text"] = detail["required_skills_text"]
                fetched += 1

            time.sleep(self.delay)

        logger.info(
            f"Detalhe: {fetched} buscadas | {skipped_by_filter} puladas pelo filtro | "
            f"{skipped_already_done} já enriquecidas antes"
        )
        return jobs


if __name__ == "__main__":
    scraper = CareerCrossScraper(delay=2.0)
    jobs = scraper.fetch_jobs()
    print(f"[CareerCross] Processamento concluído: {len(jobs)} vagas salvas em {scraper.OUTPUT_JSON}")