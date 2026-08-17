import json
from pathlib import Path

from transformers.japan_dev import normalize_japan_dev
from transformers.tokyo_dev import normalize_tokyo_dev
from transformers.careercross import normalize_careercross


RAW_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/normalized/jobs_latest.json")


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def process_source(filename, source, normalizer):

    path = RAW_DIR / filename

    if not path.exists():
        print(f"{source}: arquivo não encontrado")
        return []

    data = load_json(path)

    print(f"{source}: {len(data)} vagas")

    return normalizer(data)


def main():

    jobs = []


    jobs += process_source(
        "japan_dev.json",
        "JapanDev",
        normalize_japan_dev
    )


    jobs += process_source(
        "tokyo_dev.json",
        "TokyoDev",
        normalize_tokyo_dev
    )


    jobs += process_source(
        "careercross.json",
        "CareerCross",
        normalize_careercross
    )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            [
                job.model_dump()
                for job in jobs
            ],
            f,
            ensure_ascii=False,
            indent=2
        )


    print(
        f"Normalizadas {len(jobs)} vagas"
    )


if __name__ == "__main__":
    main()