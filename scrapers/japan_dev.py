# scrapers/japan_dev.py

import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JapanDevScraper:

    ALGOLIA_APP_ID = "8S3J8C7YSA"
    ALGOLIA_API_KEY = "9ebc037e3e423ff4aa80a065944a2b5b"
    ALGOLIA_INDEX = "Job_production"

    URL = (
        f"https://{ALGOLIA_APP_ID}-dsn.algolia.net"
        f"/1/indexes/{ALGOLIA_INDEX}/query"
    )

    RAW_JSON = Path("data/raw/japan_dev_raw.json")
    OUTPUT_JSON = Path("data/raw/japan_dev.json")


    def __init__(self):

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",

            "X-Algolia-Application-Id": self.ALGOLIA_APP_ID,
            "X-Algolia-API-Key": self.ALGOLIA_API_KEY,

            "Origin": "https://japan-dev.com",
            "Referer": "https://japan-dev.com/",

            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120 Safari/537.36"
            ),
        }


    def fetch_jobs(self) -> List[Dict[str, Any]]:

        logger.info("Buscando vagas via Algolia...")

        all_hits = []

        page = 0


        while True:

            params = {
                "query": "",
                "page": page,
                "hitsPerPage": 60,

                "facets": [
                    "candidate_location",
                    "company_is_startup",
                    "company_name",
                    "english_level_enum",
                    "japanese_level_enum",
                    "job_type_names",
                    "location",
                    "remote_level",
                    "salary_tags",
                    "seniority_level",
                    "skill_names",
                ],

                "maxValuesPerFacet": 10,

                "highlightPreTag": "__ais-highlight__",
                "highlightPostTag": "__/ais-highlight__",
            }


            encoded = urllib.parse.urlencode(
                params,
                doseq=True
            )


            try:

                response = httpx.post(
                    self.URL,
                    headers=self.headers,
                    json={
                        "params": encoded
                    },
                    timeout=20
                )


                response.raise_for_status()

                data = response.json()


                hits = data.get(
                    "hits",
                    []
                )


                nb_pages = data.get(
                    "nbPages",
                    0
                )


                logger.info(
                    f"Página {page+1}/{nb_pages}: "
                    f"{len(hits)} vagas"
                )


                all_hits.extend(hits)


                if page >= nb_pages - 1:
                    break


                page += 1


            except Exception as e:

                logger.exception(
                    f"Erro Algolia página {page}: {e}"
                )

                break



        logger.info(
            f"Total bruto Algolia: {len(all_hits)}"
        )


        self._save_json(
            self.RAW_JSON,
            all_hits
        )


        jobs = self._normalize(
            all_hits
        )


        self._save_json(
            self.OUTPUT_JSON,
            jobs
        )


        logger.info(
            f"JSON final criado: {self.OUTPUT_JSON}"
        )


        return jobs



    def _normalize(
        self,
        hits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:


        jobs = []

        now = datetime.now(
            timezone.utc
        ).isoformat()



        for item in hits:


            object_id = item.get(
                "objectID"
            )

            title = item.get(
                "title"
            )


            if not title:
                continue



            company = item.get(
                "company",
                {}
            )


            company_name = (
                company.get("name")
                if isinstance(company, dict)
                else item.get("company_name")
            )


            company_slug = (
                company.get("slug")
                if isinstance(company, dict)
                else None
            )



            skills = item.get(
                "skills",
                []
            )


            technologies = []


            for skill in skills:

                if isinstance(skill, dict):

                    name = skill.get(
                        "name"
                    )

                    if name:
                        technologies.append(
                            name
                        )


            if not technologies:

                technologies = item.get(
                    "skill_names",
                    []
                )



            jobs.append({

                "id":
                    f"jdev-{object_id}",


                "title":
                    title,


                "company": {

                    "name":
                        company_name or "N/A",

                    "slug":
                        company_slug
                },


                "location": {

                    "city":
                        item.get("location"),

                    "country":
                        "Japan",

                    "remote_level":
                        item.get("remote_level")
                },


                "salary": {

                    "currency":
                        "JPY",

                    "min_annual":
                        item.get("salary_min"),

                    "max_annual":
                        item.get("salary_max"),

                    "tags":
                        item.get(
                            "salary_tags",
                            []
                        )
                },


                "requirements": {

                    "japanese_level":
                        item.get(
                            "japanese_level"
                        ),

                    "english_level":
                        item.get(
                            "english_level"
                        ),

                    "technologies":
                        technologies
                },


                "visa_sponsorship":
                    "Sponsors Visas"
                    in item.get(
                        "company_tag_names",
                        []
                    ),


                "company_tags":
                    item.get(
                        "company_tag_names",
                        []
                    ),


                "job_type":
                    item.get(
                        "contract_type"
                    ),


                "job_url":
                    f"https://japan-dev.com/jobs/{item.get('slug')}",


                "published_at":
                    item.get(
                        "published_at"
                    ),


                "extracted_at":
                    now
            })


        return jobs



    def _save_json(
        self,
        path: Path,
        data: Any
    ):

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )
if __name__ == "__main__":

    scraper = JapanDevScraper()

    jobs = scraper.fetch_jobs()

    print(
        f"[JapanDev] Processamento concluído: "
        f"{len(jobs)} vagas salvas em {scraper.OUTPUT_JSON}"
    )