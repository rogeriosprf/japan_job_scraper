# scripts/enrich_tokyodev.py
#
# Roda a fase 2 sobre o data/raw/tokyo_dev.json já existente: aplica o
# filtro leve do matcher (só título) e busca o detalhe só das vagas que
# passarem, capturando visa_sponsorship via o sinal "Relocate to Japan".
# Resiliente a interrupção — vagas já processadas (visa_sponsorship !=
# None) são puladas automaticamente.

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.tokyo_dev import enrich_with_details
from transformers.matcher import JobMatcher


TOKYODEV_JSON = Path("data/raw/tokyo_dev.json")


def main():
    with open(TOKYODEV_JSON, encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"Carregadas {len(jobs)} vagas de {TOKYODEV_JSON}")

    matcher = JobMatcher()
    jobs = enrich_with_details(jobs, matcher=matcher, delay=2.0)

    with open(TOKYODEV_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"Salvo de volta em {TOKYODEV_JSON}")


if __name__ == "__main__":
    main()