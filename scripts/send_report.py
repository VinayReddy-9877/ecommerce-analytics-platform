"""Preview by default; delivery requires --send and the owner's SMTP credentials."""

import argparse
import hashlib
import json
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    body = (ROOT / "reports/weekly_report.md").read_text(encoding="utf-8")
    msg = EmailMessage()
    msg["Subject"] = "Olist historical operating review"
    msg["To"] = args.to
    msg["From"] = os.getenv("SMTP_FROM", "preview@example.invalid")
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    workbook = ROOT / "reports/operating_review.xlsx"
    if workbook.exists():
        msg.add_attachment(
            workbook.read_bytes(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=workbook.name,
        )
    if not args.send:
        (ROOT / "reports/email_preview.eml").write_bytes(msg.as_bytes())
        print("Saved email_preview.eml. No message sent.")
        return
    msg.replace_header("From", os.environ["SMTP_FROM"])
    port = int(os.getenv("SMTP_PORT", "465"))
    context = ssl.create_default_context()
    if port == 465:
        client = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=context, timeout=30)
    else:
        client = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=30)
        client.ehlo()
        client.starttls(context=context)
        client.ehlo()
    with client:
        client.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        refused = client.send_message(msg)
        if refused:
            raise RuntimeError("SMTP server rejected a recipient")
    receipt = {
        "status": "accepted_by_smtp_server",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "message_id": msg["Message-ID"],
        "report_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "note": "SMTP acceptance does not prove inbox delivery. Verify the received message.",
    }
    (ROOT / "reports/email_delivery.json").write_text(json.dumps(receipt, indent=2))
    print("SMTP server accepted the report. Verify the recipient inbox.")


if __name__ == "__main__":
    main()
