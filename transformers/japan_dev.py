from models.job import (
    Job,
    Salary,
    Company,
    Location,
    Requirements,
)


def normalize_japan_dev(data):

    jobs = []

    for item in data:

        # -------------------------
        # Company
        # -------------------------

        company = item.get("company", {})

        if isinstance(company, dict):
            company_name = company.get(
                "name",
                "Unknown"
            )
            company_slug = company.get(
                "slug"
            )
        else:
            company_name = company or "Unknown"
            company_slug = None


        # -------------------------
        # Location
        # -------------------------

        location = item.get(
            "location"
        )

        if isinstance(location, dict):

            city = location.get(
                "city"
            )

            country = location.get(
                "country",
                "Japan"
            )

            remote_level = location.get(
                "remote_level"
            )

        else:

            city = location

            country = "Japan"

            remote_level = item.get(
                "remote_level"
            )


        # -------------------------
        # Skills
        # -------------------------
        # O scraper (scrapers/japan_dev.py) não salva "skills" nem
        # "skill_names" no topo do dict — a lista de tecnologias fica
        # dentro de requirements.technologies. Os dois fallbacks antigos
        # (item.get("skills"), item.get("skill_names")) nunca batiam com
        # nada, então skills sempre saía vazio pro JapanDev.

        skills = []

        raw_requirements = item.get(
            "requirements",
            {}
        )

        raw_skills = (
            raw_requirements.get("technologies", [])
            if isinstance(raw_requirements, dict)
            else []
        )

        if not raw_skills:
            # mantém compatibilidade caso o formato do raw mude no futuro
            # e volte a ter skills/skill_names no topo
            raw_skills = item.get("skills", []) or item.get("skill_names", [])

        if isinstance(raw_skills, list):

            for skill in raw_skills:

                if isinstance(skill, dict):

                    name = skill.get(
                        "name"
                    )

                    if name:
                        skills.append(
                            name.lower()
                        )

                elif isinstance(skill, str):

                    skills.append(
                        skill.lower()
                    )


        skills = sorted(
            set(skills)
        )


        # -------------------------
        # Salary
        # -------------------------

        salary = item.get(
            "salary",
            {}
        )

        if isinstance(salary, dict):

            salary_min = (
                salary.get("min")
                or salary.get("min_annual")
            )

            salary_max = (
                salary.get("max")
                or salary.get("max_annual")
            )

        else:

            salary_min = item.get(
                "salary_min"
            )

            salary_max = item.get(
                "salary_max"
            )


        # -------------------------
        # Job Model
        # -------------------------

        job = Job(

            # O scraper já monta um id único e prefixado ("jdev-XXXXX") em
            # item["id"] — não existe "objectID" no dict normalizado (isso
            # só existe no raw da Algolia, um passo antes). Usar
            # item.get("objectID") sempre retornava None, gerando o mesmo
            # job_key "JapanDev/None" pra toda vaga.
            job_key=item.get("id", "jdev-unknown"),

            source="JapanDev",


            title=item.get(
                "title",
                ""
            ),


            company=Company(

                name=company_name,

                slug=company_slug
            ),


            location=Location(

                city=city,

                country=country,

                remote_policy=remote_level,

                candidate_location=item.get(
                    "candidate_location"
                )
            ),


            salary=Salary(

                min=salary_min,

                max=salary_max,

                currency="JPY"
            ),


            skills=skills,


            requirements=Requirements(

                japanese_level=(
                    item.get(
                        "japanese_level"
                    )
                    or raw_requirements.get(
                        "japanese_level"
                    )
                    if isinstance(raw_requirements, dict)
                    else item.get("japanese_level")
                ),


                english_level=(
                    item.get(
                        "english_level"
                    )
                    or raw_requirements.get(
                        "english_level"
                    )
                    if isinstance(raw_requirements, dict)
                    else item.get("english_level")
                ),


                seniority=(
                    item.get(
                        "seniority_level"
                    )
                )
            ),


            # O scraper salva em "job_type" (já renomeado a partir de
            # contract_type na hora da raspagem) — "contract_type" não
            # existe mais nesse ponto do pipeline.
            employment_type=(
                item.get(
                    "job_type"
                )
            ),


            seniority=(
                item.get(
                    "seniority_level"
                )
            ),


            visa_sponsorship=(
                "Sponsors Visas"
                in item.get(
                    "company_tags",
                    []
                )
                or item.get(
                    "visa_sponsorship",
                    False
                )
            ),


            description=(
                item.get(
                    "description"
                )
                or item.get(
                    "content"
                )
            ),


            # O scraper já monta a URL completa em "job_url" — "url" e
            # "slug" não existem no dict, então o fallback antigo sempre
            # gerava "https://japan-dev.com/jobs/None".
            application_url=(
                item.get("job_url")
                or item.get("url")
            ),


            published_at=item.get(
                "published_at"
            ),


            extracted_at=item.get(
                "extracted_at"
            ),


            raw_payload=item
        )

        jobs.append(job)

    return jobs