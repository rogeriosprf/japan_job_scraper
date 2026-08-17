import json
import polars as pl

from transformers.matcher import JobMatcher


def main():

    with open(
        "data/normalized/jobs_latest.json",
        encoding="utf-8"
    ) as f:
        jobs = json.load(f)


    matcher = JobMatcher()


    df = matcher.rank_jobs(jobs)


    print()
    print(f"Total analisado: {len(df)} vagas")
    print()


    df = df.with_columns(

        pl.col("company")
        .map_elements(
            lambda x: x.get("name")
            if isinstance(x, dict)
            else x,
            return_dtype=pl.String
        )
        .alias("company_name")

    )


    df.select(
        [

            "fit_score",

            "technical_score",
            "role_score",
            "seniority_score",
            "visa_score",

            "title",
            "company_name",
            "source",

            "score_reasons"

        ]
    ).head(20).write_json(
        "data/processed/matcher_result.json"
    )


    print(
        df.select(
            [
                "fit_score",
                "technical_score",
                "role_score",
                "seniority_score",
                "visa_score",
                "title",
                "company_name",
                "source",
                "score_reasons"
            ]
        )
        .head(20)
    )



if __name__ == "__main__":
    main()