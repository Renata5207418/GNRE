
"""Envio de recuperação de senha pelo Microsoft Graph (Microsoft 365).

O envio requer credenciais de aplicação no Entra ID com Mail.Send.
Nunca imprime links de recuperação nem tokens em logs.
"""

from urllib.parse import quote

import requests

from app.config import settings


def email_configurado() -> bool:
    return all(
        [
            settings.M365_TENANT_ID,
            settings.M365_CLIENT_ID,
            settings.M365_CLIENT_SECRET,
            settings.M365_SENDER_EMAIL,
            settings.FRONTEND_PUBLIC_URL,
        ]
    )


def enviar_recuperacao(destinatario: str, token: str) -> None:
    """Envia link de uso único, válido por 20 min. Lança erro se falhar."""
    if not email_configurado():
        raise RuntimeError("Microsoft 365 não configurado para o GNRE.")

    tenant = settings.M365_TENANT_ID
    assert tenant is not None

    token_resposta = requests.post(
        "https://login.microsoftonline.com/"
        f"{quote(tenant, safe='')}/oauth2/v2.0/token",
        data={
            "client_id": settings.M365_CLIENT_ID,
            "client_secret": settings.M365_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=(10, 20),
    )
    token_resposta.raise_for_status()
    acesso = token_resposta.json()["access_token"]

    base = settings.FRONTEND_PUBLIC_URL.rstrip("/")
    link = f"{base}/redefinir-senha?token={quote(token, safe='')}"

    remetente = quote(settings.M365_SENDER_EMAIL, safe="")
    resposta = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{remetente}/sendMail",
        headers={
            "Authorization": f"Bearer {acesso}",
            "Content-Type": "application/json",
        },
        json={
            "message": {
                "subject": "GNRE - Recuperação de senha",
                "body": {
                    "contentType": "Text",
                    "content": (
                        "Recebemos uma solicitação para redefinir a senha "
                        "da sua conta GNRE.\n\n"
                        "Use o link abaixo em até 20 minutos:\n"
                        f"{link}\n\n"
                        "Se você não solicitou a recuperação, "
                        "ignore esta mensagem."
                    ),
                },
                "toRecipients": [
                    {"emailAddress": {"address": destinatario}}
                ],
            },
            "saveToSentItems": False,
        },
        timeout=(10, 20),
    )
    # O Graph confirma a aceitação da solicitação com HTTP 202.
    if resposta.status_code != 202:
        resposta.raise_for_status()
        raise RuntimeError("Microsoft Graph não aceitou o envio do e-mail.")
