import logging

from config.profile import PROFILE

logger = logging.getLogger(__name__)


class JobMatcher:

    def __init__(self, profile=None):

        # Se nenhum profile for passado, mantém o comportamento antigo
        # (config/profile.py fixo). O main.py passa o profile lido do
        # Supabase (matcher_profile), editável pela UI do site.
        self.profile = profile or PROFILE

    def normalize(self, text):

        if not text:
            return ""

        return text.lower().replace("\n", " ")

    def score_keywords(self, text, keywords, prefix):

        score = 0
        reasons = []

        for key, value in keywords.items():

            if key.lower() in text:

                score += value

                reasons.append(f"{prefix}:{key}+{value}")

        return score, reasons

    def should_fetch_details(self, job, threshold=-50):
        """
        Filtro leve pra decidir se vale gastar 1 request de detalhe numa
        vaga. Usado só por fontes que ainda não têm skills/description na
        listagem (hoje: CareerCross) — fontes já completas (JapanDev,
        TokyoDev) pulam isso e vão direto pro calculate_job_score.

        Roda só contra o título (único texto confiável nessa etapa) e usa
        um piso tolerante: só descarta se bater em algo claramente fora do
        perfil, pra não perder vaga boa por falta de sinal técnico no
        título (que no CareerCross costuma vir em japonês).
        """

        text = self.normalize(str(job.get("title", "")))

        avoid_score, reasons = self.score_keywords(text, self.profile["avoid"], "avoid")

        keep = avoid_score > threshold

        if not keep:
            logger.info(f"Pulando detalhe de '{job.get('title')}' — {reasons}")

        return keep

    def calculate_job_score(self, job):

        text = " ".join(
            [
                str(job.get("title", "")),
                str(job.get("description", "")),
                str(job.get("requirements", "")),
                str(job.get("skills", "")),
            ]
        )

        text = self.normalize(text)

        technical_score = 0
        role_score = 0
        seniority_score = 0
        visa_score = 0

        reasons = []

        #
        # skills
        #

        s, r = self.score_keywords(text, self.profile["core_skills"], "skill")

        technical_score += s
        reasons += r

        #
        # secondary
        #

        s, r = self.score_keywords(text, self.profile["secondary_skills"], "secondary")

        technical_score += s
        reasons += r

        #
        # roles
        #

        s, r = self.score_keywords(text, self.profile["roles"], "role")

        role_score += s
        reasons += r

        #
        # avoid
        #

        s, r = self.score_keywords(text, self.profile["avoid"], "avoid")

        technical_score += s
        reasons += r

        #
        # senioridade
        #

        s, r = self.score_keywords(text, self.profile["seniority"], "level")

        seniority_score += s
        reasons += r

        #
        # idioma
        #

        s, r = self.score_keywords(text, self.profile["language"], "language")

        visa_score += s
        reasons += r

        #
        # bonus visto
        #

        # visa_sponsorship é bool (True/False/None) no schema do Job — não
        # string. O código antigo fazia str(job.get("visa_sponsorship",""))
        # e procurava "yes"/"sponsor" nisso, o que nunca batia (str(True)
        # vira "true", não contém nenhuma das duas). Corrigido pra checar
        # o bool diretamente.

        if job.get("visa_sponsorship") is True:

            visa_score += 50

            reasons.append("visa:sponsor+50")

        fit_score = technical_score + role_score + seniority_score + visa_score

        return {
            "technical_score": technical_score,
            "role_score": role_score,
            "seniority_score": seniority_score,
            "visa_score": visa_score,
            "fit_score": fit_score,
            "score_reasons": reasons,
        }

    def rank_jobs(self, jobs):

        ranked = []

        for job in jobs:

            score = self.calculate_job_score(job)

            item = dict(job)

            item.update(score)

            ranked.append(item)

        ranked.sort(key=lambda x: x["fit_score"], reverse=True)

        logger.info(f"Ranking concluído: {len(ranked)} vagas")

        import polars as pl

        # infer_schema_length=None faz o polars escanear TODAS as linhas
        # antes de decidir o tipo de cada coluna, em vez de só as
        # primeiras 100 (default). Como a lista já vem ordenada por
        # fit_score aqui, as primeiras ~100 são sempre as de maior score
        # — se por acaso description (ou outro campo) vier None com mais
        # frequência nelas numa rodada específica, o polars concluía
        # "coluna vazia" e quebrava ao encontrar um valor de texto de
        # verdade mais adiante na lista. Com 1036 linhas o custo de
        # escanear tudo é irrelevante.
        return pl.DataFrame(ranked, infer_schema_length=None)
