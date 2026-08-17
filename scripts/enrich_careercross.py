# scripts/enrich_careercross.py
#
# Roda a fase 2 sobre o data/raw/careercross.json já existente: aplica o
# filtro leve do matcher (só título) e busca o detalhe só das vagas que
# passarem. Pode ser interrompido e retomado — vagas já enriquecidas
# (com description preenchido) são puladas automaticamente.

import json
import sys
from pathlib import Path

# Garante que a raiz do projeto está no sys.path, independente de como o
# script é chamado (python3 scripts/enrich_careercross.py roda com
# scripts/ como sys.path[0], não a raiz — por isso "import scrapers"
# falhava com ModuleNotFoundError).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.careercross import CareerCrossScraper
from transformers.matcher import JobMatcher


CAREERCROSS_JSON = Path("data/raw/careercross.json")


def main():
    with open(CAREERCROSS_JSON, encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"Carregadas {len(jobs)} vagas de {CAREERCROSS_JSON}")

    matcher = JobMatcher()
    scraper = CareerCrossScraper(delay=2.5)

    jobs = scraper.enrich_with_details(jobs, matcher=matcher)

    with open(CAREERCROSS_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"Salvo de volta em {CAREERCROSS_JSON}")


if __name__ == "__main__":
    main()