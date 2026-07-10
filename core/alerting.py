"""
Alerting mínimo para SIVE (Ola 2 de la auditoría: antes había CERO alertas).

`notify_failure(source, detail)` registra siempre y, si hay canal configurado por
entorno, envía por webhook (estilo Slack/Discord/Teams) y/o email. Es no-op silencioso
si no hay nada configurado, y deduplica alertas iguales en una ventana para no spamear.

Activación (en .env):
- ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...   (o Discord/Teams/genérico)
- ALERT_EMAIL_TO=ops@udenar.edu.co   (requiere EMAIL_HOST/EMAIL_* configurados)
"""
import json
import logging
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_DEDUP_MINUTES = 30


def notify_failure(source, detail, dedup_minutes=DEFAULT_DEDUP_MINUTES):
    """Notifica un fallo por los canales configurados. Nunca lanza excepción (el
    alerting jamás debe romper el flujo que lo invoca)."""
    subject = f"[SIVE] Fallo: {source}"
    message = f"{subject}\n\n{detail}"
    logger.error("ALERTA: %s | %s", source, detail)

    # Dedup: la misma fuente no re-alerta dentro de la ventana (cache.add es atómico).
    try:
        if not cache.add(f"alert:{source}", 1, dedup_minutes * 60):
            return
    except Exception:  # noqa: BLE001 — sin caché, seguimos e intentamos notificar
        pass

    _send_webhook(message)
    _send_email(subject, message)


def _send_webhook(message):
    url = (getattr(settings, "ALERT_WEBHOOK_URL", "") or "").strip()
    if not url:
        return
    try:
        # 'text' es el campo que aceptan Slack/Discord/Teams y la mayoría de webhooks.
        data = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)  # noqa: S310 — URL de confianza (env)
    except Exception as exc:  # noqa: BLE001
        logger.error("Alerting: no se pudo enviar al webhook: %s", exc)


def _send_email(subject, message):
    to = (getattr(settings, "ALERT_EMAIL_TO", "") or "").strip()
    if not to or not getattr(settings, "EMAIL_HOST", ""):
        return
    try:
        from django.core.mail import send_mail
        recipients = [x.strip() for x in to.split(",") if x.strip()]
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "sive@localhost"),
            recipients,
            fail_silently=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Alerting: no se pudo enviar el email: %s", exc)
