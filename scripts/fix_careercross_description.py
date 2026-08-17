# scripts/fix_careercross_description.py
#
# Corrige data/raw/careercross.json: o required_skills_text (seção
# "【必須要件】" da página de detalhe, com a stack técnica exigida) foi
# salvo em raw_payload mas nunca entrava no texto que o matcher usa pra
# pontuar (calculate_job_score só lê description/requirements/skills).
# Isso fazia o score ignorar keywords técnicas que só apareciam nessa
# seção — confirmado em 191 de 646 vagas.
#
# Fix: mescla required_skills_text dentro de description, sem re-raspar
# nada (o dado já está salvo em raw_payload). Idempotente — rodar de novo
# não duplica o texto.

import json
from pathlib import Path

CAREERCROSS_JSON = Path("data/raw/careercross.json")
MARKER = "\n\n【必須要件・required skills】\n"


def main():
    with open(CAREERCROSS_JSON, encoding="utf-8") as f:
        jobs = json.load(f)

    fixed = 0
    already_ok = 0
    no_data = 0

    for job in jobs:
        description = job.get("description") or ""
        required_skills = (job.get("raw_payload") or {}).get("required_skills_text")

        if not required_skills:
            no_data += 1
            continue

        if MARKER in description:
            already_ok += 1
            continue

        job["description"] = description + MARKER + required_skills
        fixed += 1

    with open(CAREERCROSS_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"Corrigidas: {fixed} | já estavam ok: {already_ok} | sem required_skills_text: {no_data}")


if __name__ == "__main__":
    main()