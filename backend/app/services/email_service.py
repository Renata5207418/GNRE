import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import quote
from app.config import settings


def email_configurado() -> bool:
    return all(
        [
            settings.SMTP_SERVER,
            settings.SMTP_PORT > 0,
            settings.SMTP_USER,
            settings.SMTP_PASSWORD,
            settings.FRONTEND_PUBLIC_URL,
        ]
    )


def enviar_recuperacao(destinatario: str, token: str) -> None:
    """Envia link de recuperação de senha válido por 20 minutos."""

    if not email_configurado():
        raise RuntimeError("SMTP não configurado para o GNRE.")

    base = settings.FRONTEND_PUBLIC_URL.rstrip("/")
    link = f"{base}/redefinir-senha?token={quote(token, safe='')}"
    link_html = escape(link, quote=True)
    mensagem = EmailMessage()

    mensagem["Subject"] = "GNRE | Redefinição de senha"
    mensagem["From"] = formataddr(
        ("GNRE | Scryta", settings.SMTP_USER)
    )
    mensagem["To"] = destinatario

    # Versão texto para clientes que não exibem HTML.
    mensagem.set_content(
        "GNRE - Redefinição de senha\n\n"
        "Olá!\n\n"
        "Recebemos uma solicitação para redefinir a senha "
        "da sua conta na plataforma GNRE.\n\n"
        "Acesse o link abaixo para criar uma nova senha:\n\n"
        f"{link}\n\n"
        "Este link expira em 20 minutos e pode ser utilizado "
        "apenas uma vez.\n\n"
        "Se você não solicitou essa alteração, ignore "
        "esta mensagem. Sua senha atual continuará funcionando.\n\n"
        "GNRE | Scryta Contabilidade\n"
        "Mensagem automática. Não é necessário responder."
    )

    # Versão HTML com identidade visual da plataforma.
    html = f"""\
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>GNRE - Redefinição de senha</title>
        </head>
        <body style="margin:0;padding:0;background-color:#f3f5f6;
                     font-family:Arial,Helvetica,sans-serif;">
        
        <table role="presentation" cellpadding="0" cellspacing="0"
               border="0" width="100%"
               style="background-color:#f3f5f6;">
            <tr>
                <td align="center" style="padding:36px 16px;">
        
                    <table role="presentation" cellpadding="0" cellspacing="0"
                           border="0" width="100%"
                           style="max-width:560px;background-color:#ffffff;
                                  border:1px solid #e1e7eb;">
        
                        <!-- CABEÇALHO -->
                        <tr>
                            <td align="center"
                                style="background-color:#103f53;padding:32px 24px;">
        
                                <div style="font-size:34px;font-weight:bold;
                                            color:#ffffff;letter-spacing:1px;">
                                    GNRE
                                </div>
        
                                <div style="font-size:11px;color:#c1d9e2;
                                            letter-spacing:2px;margin-top:8px;">
                                    PLATAFORMA DE GESTÃO DE GUIAS
                                </div>
        
                            </td>
                        </tr>
        
                        <!-- CONTEÚDO -->
                        <tr>
                            <td style="padding:36px 32px 30px;">
        
                                <h1 style="margin:0 0 24px;
                                           font-size:24px;
                                           color:#163648;">
                                    Redefinição de senha
                                </h1>
        
                                <p style="font-size:15px;
                                          line-height:24px;
                                          color:#435462;">
                                    Olá!
                                </p>
        
                                <p style="font-size:15px;
                                          line-height:24px;
                                          color:#435462;">
                                    Recebemos uma solicitação para redefinir
                                    a senha da sua conta na plataforma
                                    <strong>GNRE</strong>.
                                </p>
        
                                <p style="font-size:15px;
                                          line-height:24px;
                                          color:#435462;">
                                    Para criar uma nova senha, clique no
                                    botão abaixo:
                                </p>
        
                                <!-- BOTÃO -->
                                <table role="presentation"
                                       cellpadding="0" cellspacing="0"
                                       border="0" align="center"
                                       style="margin:30px auto;">
                                    <tr>
                                        <td align="center"
                                            bgcolor="#104960"
                                            style="background-color:#104960;
                                                   padding:15px 28px;">
                                            <a href="{link_html}"
                                               style="display:inline-block;
                                                      color:#ffffff;
                                                      font-size:15px;
                                                      font-weight:bold;
                                                      text-decoration:none;">
                                                Redefinir minha senha
                                            </a>
                                        </td>
                                    </tr>
                                </table>
        
                                <!-- AVISO DE EXPIRAÇÃO -->
                                <table role="presentation"
                                       cellpadding="0" cellspacing="0"
                                       border="0" width="100%"
                                       style="background-color:#f5f7f8;">
                                    <tr>
                                        <td style="padding:18px 20px;">
        
                                            <p style="margin:0 0 8px;
                                                      font-size:14px;
                                                      color:#405362;
                                                      font-weight:bold;">
                                                Este link expira em 20 minutos.
                                            </p>
        
                                            <p style="margin:0;
                                                      font-size:13px;
                                                      line-height:20px;
                                                      color:#61717c;">
                                                Por segurança, o link pode
                                                ser utilizado apenas uma vez.
                                            </p>
        
                                        </td>
                                    </tr>
                                </table>
        
                                <p style="font-size:13px;
                                          line-height:21px;
                                          color:#61717c;
                                          margin-top:28px;">
                                    Se você não solicitou essa alteração,
                                    ignore esta mensagem. Sua senha atual
                                    continuará funcionando.
                                </p>
        
                                <p style="font-size:12px;
                                          line-height:19px;
                                          color:#80909a;
                                          margin-top:25px;">
                                    Se o botão não funcionar, copie e cole
                                    este endereço no navegador:
                                </p>
        
                                <p style="font-size:12px;
                                          line-height:19px;
                                          overflow-wrap:anywhere;
                                          word-break:break-all;">
                                    <a href="{link_html}"
                                       style="color:#104960;">
                                        {link_html}
                                    </a>
                                </p>
        
                            </td>
                        </tr>
        
                        <!-- RODAPÉ -->
                        <tr>
                            <td align="center"
                                style="background-color:#f5f7f8;
                                       border-top:1px solid #e1e7eb;
                                       padding:22px 20px;">
        
                                <p style="margin:0 0 8px;
                                          font-size:12px;
                                          color:#80909a;">
                                    © 2026 GNRE | Scryta Contabilidade
                                </p>
        
                                <p style="margin:0;
                                          font-size:11px;
                                          color:#80909a;">
                                    Mensagem automática.
                                    Não é necessário responder.
                                </p>
        
                            </td>
                        </tr>
        
                    </table>
        
                </td>
            </tr>
        </table>
        
        </body>
        </html>
        """

    mensagem.add_alternative(html, subtype="html")

    # Conexão segura com o SMTP.
    contexto_ssl = ssl.create_default_context()

    with smtplib.SMTP(
        host=settings.SMTP_SERVER,
        port=settings.SMTP_PORT,
        timeout=30,
    ) as servidor:

        servidor.ehlo()
        servidor.starttls(context=contexto_ssl)
        servidor.ehlo()
        servidor.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        servidor.send_message(mensagem)
