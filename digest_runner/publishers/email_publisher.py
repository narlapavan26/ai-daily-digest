"""
digest_runner/publishers/email_publisher.py
===========================================
Purpose:
  Send digest via SMTP.
  Reads the Markdown file, converts it to HTML, and sends a multipart email.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from pathlib import Path

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# pyrefly: ignore [missing-import]
from digest_runner.config.settings import settings

logger = logging.getLogger(__name__)

def publish_to_email(digest_path: str, total_items: int) -> bool:
    """Publish the digest via SMTP Email."""
    server = settings.smtp_server
    port = settings.smtp_port
    user = settings.smtp_username
    pwd = settings.smtp_password
    to_emails = settings.email_to
    from_email = settings.email_from
    
    if not all([server, user, pwd, to_emails, from_email]):
        logger.info("Email publisher skipped (SMTP configs incomplete).")
        return False

    path = Path(digest_path)
    if not path.exists():
        logger.error(f"Email publisher failed: file {digest_path} not found.")
        return False

    logger.info("Publishing digest via Email...")
    
    with open(path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    if HAS_MARKDOWN:
        # Include extensions for tables, fenced code blocks, etc.
        html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
        # Add basic styling
        html_content = f"<html><body style='font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;'>{html_content}</body></html>"
    else:
        logger.warning("Markdown library not installed. Falling back to plain text email.")
        html_content = f"<html><body><pre>{md_content}</pre></body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Daily Digest ({path.name})"
    msg["From"] = from_email
    msg["To"] = to_emails  # Note: basic comma separated list

    # Attach both plain and HTML
    msg.attach(MIMEText(md_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.send_message(msg)
        logger.info("Successfully published via Email!")
        return True
    except Exception as e:
        logger.error(f"Failed to publish via Email: {e}")
        return False
