from models.job import (
    Job,
    Salary,
    Company,
    Location,
    Requirements,
)


def normalize_tokyo_dev(data):

    jobs = []

    for item in data:

        company = item.get("company", "Unknown")

        salary = item.get("salary") or {}

        job = Job(

            job_key=item.get(
                "job_key"
            ),

            source="TokyoDev",

            title=item.get(
                "title",
                ""
            ),

            company=Company(
                name=company
            ),

            location=Location(
                city=None,
                country="Japan",
                remote_policy=item.get(
                    "remote_policy"
                ),
                candidate_location=item.get(
                    "applicant_location"
                )
            ),

            salary=Salary(
                min=salary.get(
                    "min"
                ),

                max=salary.get(
                    "max"
                ),

                currency=salary.get(
                    "currency",
                    "JPY"
                ),

                text=salary.get(
                    "text"
                )
            ),

            skills=[
                s.lower()
                for s in item.get(
                    "stack",
                    []
                )
            ],

            requirements=Requirements(
                japanese_level=item.get(
                    "japanese_level"
                ),

                english_level=None,

                seniority=None
            ),

            employment_type=None,

            seniority=None,

            visa_sponsorship=(
                "Apply from abroad"
                in item.get(
                    "japanese_level",
                    ""
                )
                or
                "abroad"
                in item.get(
                    "applicant_location",
                    ""
                ).lower()
            ),

            description=None,

            application_url=item.get(
                "url"
            ),

            published_at=None,

            extracted_at=None,

            raw_payload=item
        )


        jobs.append(job)


    return jobs