"""Failure notification; requires explicitly configured SMTP recipient and secrets."""

import os
import smtplib
import ssl
from email.message import EmailMessage


def main():
    names = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_TO"]
    if not all(os.getenv(k) for k in names):
        print("::warning::Failure alert not sent: SMTP configuration is incomplete.")
        return
    msg = EmailMessage()
    msg["Subject"] = "Olist pipeline failed"
    msg["From"], msg["To"] = os.environ["SMTP_FROM"], os.environ["SMTP_TO"]
    msg.set_content(
        "The reporting pipeline failed. Inspect the run and retained artifacts: "
        + os.getenv("RUN_URL", "local run")
    )
    with smtplib.SMTP_SSL(
        os.environ["SMTP_HOST"],
        int(os.getenv("SMTP_PORT", "465")),
        context=ssl.create_default_context(),
        timeout=30,
    ) as client:
        client.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        client.send_message(msg)


if __name__ == "__main__":
    main()
