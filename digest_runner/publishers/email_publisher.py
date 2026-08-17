"""
digest_runner/publishers/email_publisher.py
===========================================
Purpose:
  Send digest via SMTP.
  Reads the Markdown file, converts it to HTML, and sends a multipart email.

Recipient resolution (in priority order):
  1. digest_runner/config/recipients.yaml  ← edit this file to add/remove emails
  2. EMAIL_TO env var / settings.email_to  ← fallback (comma-separated)

To add or remove a subscriber, just edit recipients.yaml and commit.
No .env or GitHub Secrets update is needed.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from pathlib import Path
from typing import List

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# pyrefly: ignore [missing-import]
from digest_runner.config.settings import settings

logger = logging.getLogger(__name__)

# Path to the committed recipients file (relative to this file → go up 2 levels)
_RECIPIENTS_FILE = Path(__file__).parent.parent / "config" / "recipients.yaml"


def _load_recipients() -> List[str]:
    """
    Load recipients from recipients.yaml (committed to repo).

    Falls back to settings.email_to (EMAIL_TO env var) if:
      - yaml file is missing
      - yaml library is not installed
      - yaml file has no recipients listed

    Returns a deduplicated, stripped list of email addresses.
    """
    recipients: List[str] = []

    # ── Step 1: try loading from committed YAML file ─────────────────────────
    if HAS_YAML and _RECIPIENTS_FILE.exists():
        try:
            data = yaml.safe_load(_RECIPIENTS_FILE.read_text(encoding="utf-8"))
            from_file = data.get("recipients", []) if isinstance(data, dict) else []
            recipients = [str(e).strip() for e in from_file if str(e).strip()]
            if recipients:
                logger.info(
                    "Email recipients loaded from %s: %d addresses",
                    _RECIPIENTS_FILE.name,
                    len(recipients),
                )
        except Exception as exc:
            logger.warning("Could not load %s: %s — falling back to env var", _RECIPIENTS_FILE.name, exc)
            recipients = []

    # ── Step 2: fallback to EMAIL_TO env var ─────────────────────────────────
    if not recipients and settings.email_to:
        recipients = [e.strip() for e in settings.email_to.split(",") if e.strip()]
        logger.info(
            "Email recipients loaded from EMAIL_TO env var: %d addresses", len(recipients)
        )

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for addr in recipients:
        if addr.lower() not in seen:
            seen.add(addr.lower())
            deduped.append(addr)

    return deduped


def publish_to_email(digest_path: str, total_items: int) -> bool:
    """Publish the digest via SMTP Email."""
    server   = settings.smtp_server
    port     = settings.smtp_port
    user     = settings.smtp_username
    pwd      = settings.smtp_password
    from_email = settings.email_from

    if not all([server, user, pwd, from_email]):
        logger.info("Email publisher skipped (SMTP configs incomplete).")
        return False

    # ── Resolve recipients ────────────────────────────────────────────────────
    recipients = _load_recipients()
    if not recipients:
        logger.warning("Email publisher skipped: no recipients found in recipients.yaml or EMAIL_TO.")
        return False

    path = Path(digest_path)
    if not path.exists():
        logger.error("Email publisher failed: file %s not found.", digest_path)
        return False

    logger.info("Publishing digest via Email to %d recipients: %s", len(recipients), recipients)

    with open(path, "r", encoding="utf-8") as f:
        md_content = f.read()

    if HAS_MARKDOWN:
        html_content = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
        css_style = """
        <style>
            /* Shadcn/Aceternity Inspired Email UI */
            body {
                font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 40px 20px;
                background-color: #fafafa;
                color: #09090b; /* zinc-950 */
                line-height: 1.7;
                -webkit-font-smoothing: antialiased;
            }
            .email-container {
                background: #ffffff;
                padding: 48px;
                border-radius: 16px;
                border: 1px solid #e4e4e7; /* zinc-200 */
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
            }
            h1 { color: #09090b; border-bottom: 1px solid #e4e4e7; padding-bottom: 16px; text-align: left; font-size: 30px; font-weight: 700; letter-spacing: -0.025em; }
            h2 { color: #18181b; margin-top: 48px; font-size: 24px; font-weight: 600; letter-spacing: -0.025em; }
            h3 { color: #27272a; font-size: 18px; font-weight: 600; margin-bottom: 8px; }
            p { color: #3f3f46; /* zinc-700 */ font-size: 15px; }
            a { color: #09090b; text-decoration: underline; text-underline-offset: 4px; font-weight: 500; transition: color 0.2s; }
            a:hover { color: #71717a; } /* zinc-500 */
            blockquote {
                border-left: 2px solid #09090b;
                background: #f4f4f5; /* zinc-100 */
                margin: 24px 0;
                padding: 16px 24px;
                border-radius: 0 8px 8px 0;
                font-style: normal;
                color: #27272a; /* zinc-800 */
                font-size: 15px;
            }
            hr { border: 0; height: 1px; background: #e4e4e7; margin: 40px 0; }
            ul { padding-left: 24px; color: #3f3f46; }
            li { margin-bottom: 8px; }
            table { width: 100%; border-collapse: collapse; margin: 32px 0; font-size: 14px; text-align: left; }
            th, td { padding: 12px 16px; border-bottom: 1px solid #e4e4e7; }
            th { color: #71717a; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; font-size: 12px; }
            td { color: #3f3f46; }
            code { background-color: #f4f4f5; color: #09090b; padding: 2px 6px; border-radius: 4px; font-size: 0.875em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; border: 1px solid #e4e4e7; }
            pre { background-color: #09090b; color: #fafafa; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 14px; }
            pre code { background-color: transparent; color: inherit; padding: 0; border: none; }
        </style>
        """
        html_content = (
            f"<html><head>{css_style}</head><body>"
            f"<div class='email-container'>"
            f"{html_content}"
            f"</div></body></html>"
        )
    else:
        logger.warning("Markdown library not installed. Falling back to plain text email.")
        html_content = f"<html><body><pre>{md_content}</pre></body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"]  = f"⚡ AI Daily Digest — {path.stem.replace('digest_', '')}"
    msg["From"]     = from_email
    msg["To"]       = ", ".join(recipients)

    msg.attach(MIMEText(md_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            # send_message honours the To: header list automatically
            smtp.sendmail(from_email, recipients, msg.as_string())
        logger.info("Successfully published via Email to %d recipients!", len(recipients))
        return True
    except Exception as e:
        logger.error("Failed to publish via Email: %s", e)
        return False
