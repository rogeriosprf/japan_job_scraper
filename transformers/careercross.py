# transformers/careercross.py
#
# Obs: não tenho acesso ao transformers/japan_dev.py nem ao
# transformers/tokyo_dev.py do seu projeto, então não sei se eles fazem
# algum mapeamento/limpeza extra além de instanciar o Job. Como o
# CareerCrossScraper já salva os dicts bem próximos do schema do Job,
# esse normalizer é quase direto — ajuste se seu padrão fizer algo a mais
# (dedupe, validação de campos obrigatórios, etc.) que eu não tenha replicado.

from typing import Any, Dict, List

from models.job import Company, Job, Location, Requirements, Salary


def normalize_careercross(data: List[Dict[str, Any]]) -> List[Job]:
    jobs: List[Job] = []

    for item in data:
        try:
            company_data = item.get("company") or {}
            location_data = item.get("location") or {}
            salary_data = item.get("salary")
            requirements_data = item.get("requirements") or {}

            job = Job(
                job_key=item["job_key"],
                source=item.get("source", "CareerCross"),
                title=item["title"],
                company=Company(
                    name=company_data.get("name", "N/A"),
                    slug=company_data.get("slug"),
                ),
                location=Location(
                    city=location_data.get("city"),
                    country=location_data.get("country", "Japan"),
                    remote_policy=location_data.get("remote_policy"),
                    candidate_location=location_data.get("candidate_location"),
                ),
                salary=Salary(**salary_data) if salary_data else None,
                skills=item.get("skills", []),
                requirements=Requirements(
                    japanese_level=requirements_data.get("japanese_level"),
                    english_level=requirements_data.get("english_level"),
                    seniority=requirements_data.get("seniority"),
                ),
                employment_type=item.get("employment_type"),
                visa_sponsorship=item.get("visa_sponsorship"),
                job_language=item.get("job_language"),
                active=item.get("active"),
                description=item.get("description"),
                application_url=item.get("application_url"),
                published_at=item.get("published_at"),
                extracted_at=item.get("extracted_at"),
                raw_payload=item.get("raw_payload"),
            )
            jobs.append(job)
        except Exception as e:
            print(f"[CareerCross] Erro ao normalizar vaga {item.get('job_key')}: {e}")

    return jobs