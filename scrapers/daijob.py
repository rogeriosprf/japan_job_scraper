# scrapers/daijob.py
import logging
from typing import Any, Dict, List
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DaijobScraper:
    BASE_URL = "https://www.daijob.com/en/jobs/search_result"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_jobs(self, keyword: str = "data engineer") -> List[Dict[str, Any]]:
        logger.info(f"Buscando vagas no Daijob com termo: '{keyword}'...")
        params = {"keyword": keyword}

        try:
            response = httpx.get(self.BASE_URL, headers=self.headers, params=params, follow_redirects=True, timeout=15.0)
            response.raise_for_status()
        except httpx.HTTPError as err:
            logger.error(f"Erro ao acessar Daijob: {err}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Pega qualquer link de detalhe de vaga na listagem
        links = soup.select("a[href*='/en/jobs/detail/']")
        jobs: List[Dict[str, Any]] = []
        seen_urls = set()

        for a in links:
            href = a.get("href", "")
            title = a.get_text(strip=True)
            
            if not href or len(title) < 3 or href in seen_urls:
                continue

            seen_urls.add(href)
            full_url = href if href.startswith("http") else f"https://www.daijob.com{href}"
            clean_id = href.strip("/").split("/")[-1]

            jobs.append({
                "source": "Daijob",
                "id": str(clean_id),
                "title": str(title),
                "company": "Daijob Listed Company",
                "location": "Japan",
                "salary_min": None,
                "salary_max": None,
                "visa_sponsorship": True,
                "japanese_level": "Bilingual / English",
                "remote_level": "Unknown",
                "technologies": [keyword],
                "url": str(full_url),
            })

        logger.info(f"Sucesso! {len(jobs)} vagas extraídas do Daijob.")
        return jobs