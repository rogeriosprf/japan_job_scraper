# notifiers/telegram.py
import os
import logging
from typing import List, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def format_salary(self, min_sal: Any, max_sal: Any) -> str:
        """Formata a faixa salarial de forma amigável em JPY."""
        if not min_sal and not max_sal:
            return "Não informado"

        def to_m(val):
            return f"¥{val / 1_000_000:.1f}M" if val >= 1_000_000 else f"¥{val:,.0f}"

        if min_sal and max_sal:
            return f"{to_m(min_sal)} - {to_m(max_sal)} / ano"
        elif min_sal:
            return f"A partir de {to_m(min_sal)} / ano"
        return f"Até {to_m(max_sal)} / ano"

    def format_visa(self, visa_sponsorship: Any) -> str:
        """
        Três estados, não dois: True/False/None (desconhecido) são
        diferentes e não podem cair no mesmo texto. job.get(chave, default)
        só usa o default se a CHAVE não existir — como nosso dado sempre
        tem a chave presente (com valor None quando desconhecido), usar
        default=True aqui escondia None atrás de "No Sponsorship".
        """
        if visa_sponsorship is True:
            return "✅ Sponsor / Relocation"
        elif visa_sponsorship is False:
            return "⚠️ Provavelmente não"
        return "❔ Não informado"

    def build_message(self, job: Dict[str, Any]) -> str:
        """Monta a mensagem em HTML limpo e escaneável."""
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        source = job.get("source", "Web")
        match_score = job.get("match_score", 0)
        url = job.get("url") or job.get("application_url", "#")

        salary_str = self.format_salary(job.get("salary_min"), job.get("salary_max"))

        techs = job.get("technologies", [])
        if isinstance(techs, str):
            techs = [t.strip() for t in techs.split(",") if t.strip()]

        techs_str = ", ".join(f"<code>{t}</code>" for t in techs[:6]) if techs else "Não especificadas"

        visa = self.format_visa(job.get("visa_sponsorship"))
        jp_level = job.get("japanese_level") or "Not Specified"

        msg = (
            f"🚀 <b>NOVA VAGA | Score: {match_score} pts</b>\n"
            f"<i>Fonte: {source}</i>\n\n"
            f"💼 <b>{title}</b>\n"
            f"🏢 <b>{company}</b>\n"
            f"📍 Japão\n\n"
            f"💵 <b>Salário:</b> {salary_str}\n"
            f"🛂 <b>Visto:</b> {visa}\n"
            f"🗣️ <b>Japonês:</b> {jp_level}\n"
            f"🛠️ <b>Stack:</b> {techs_str}\n\n"
            f"🔗 <a href='{url}'>Ver Detalhes e Aplicar no {source}</a>"
        )
        return msg

    def _send(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            response = httpx.post(self.base_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
        except Exception as err:
            logger.error(f"Erro ao enviar mensagem no Telegram: {err}")
            return False

    def send_job_alert(self, job: Dict[str, Any]) -> bool:
        """Envia uma vaga nova individualmente. Usado no dia a dia (fora
        da carga inicial), pra toda vaga nova, sem filtro de score."""
        ok = self._send(self.build_message(job))
        if ok:
            logger.info(f"Alerta enviado: {job.get('title')} ({job.get('company')})")
        return ok

    def send_new_jobs(self, jobs: List[Dict[str, Any]]) -> List[str]:
        """
        Manda um alerta individual por vaga nova. Retorna a lista de
        job_key das que foram enviadas com sucesso (pra marcar
        notified_at só nessas).
        """
        sent_keys = []
        for job in jobs:
            if self.send_job_alert(job):
                sent_keys.append(job.get("job_key"))
        return sent_keys

    def send_summary(self, jobs: List[Dict[str, Any]]) -> bool:
        """
        Uma mensagem só com a contagem — usado na carga inicial (banco
        vazio), onde notificar vaga por vaga seria uma enxurrada.
        """
        if not jobs:
            return False

        by_source: Dict[str, int] = {}
        for job in jobs:
            src = job.get("source", "Unknown")
            by_source[src] = by_source.get(src, 0) + 1

        lines = "\n".join(f"  • {src}: {count}" for src, count in sorted(by_source.items()))

        top = sorted(jobs, key=lambda j: j.get("match_score", 0), reverse=True)[:5]
        top_lines = "\n".join(
            f"  {i+1}. {j.get('title')} — {j.get('company')} ({j.get('match_score')} pts)"
            for i, j in enumerate(top)
        )

        msg = (
            f"📦 <b>Carga inicial concluída</b>\n\n"
            f"Total: <b>{len(jobs)}</b> vagas\n"
            f"{lines}\n\n"
            f"<b>Top 5 por score:</b>\n{top_lines}\n\n"
            f"A partir de agora, cada vaga nova vira uma notificação individual."
        )

        ok = self._send(msg)
        if ok:
            logger.info(f"Resumo da carga inicial enviado: {len(jobs)} vagas.")
        return ok

    def send_high_match_alerts(self, jobs: List[Dict[str, Any]], top_n: int = 5):
        """Mantido por compatibilidade — envia só as top_n por score."""
        sorted_jobs = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)[:top_n]
        for job in sorted_jobs:
            self.send_job_alert(job)