"""
digest_runner/publishers/telegram_publisher.py
==============================================
Purpose:
  Post digest to Telegram using Bot API.
  Uses sendDocument to upload the markdown file, along with a caption.
"""

import httpx
import logging
from pathlib import Path

# pyrefly: ignore [missing-import]
from digest_runner.config.settings import settings

logger = logging.getLogger(__name__)

def publish_to_telegram(digest_path: str, total_items: int) -> bool:
    """Publish the digest to Telegram via sendDocument."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    
    if not token or not chat_id:
        logger.info("Telegram publisher skipped (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured).")
        return False

    path = Path(digest_path)
    if not path.exists():
        logger.error(f"Telegram publisher failed: file {digest_path} not found.")
        return False

    logger.info("Publishing digest to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    caption = f"🚀 *AI Daily Digest is ready!*\nFound *{total_items}* high-signal items today. See attached document."

    try:
        with open(path, "rb") as f:
            files = {"document": (path.name, f, "text/markdown")}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "Markdown"
            }
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, data=data, files=files)
                response.raise_for_status()
                
        logger.info("Successfully published to Telegram!")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to Telegram: {e}")
        return False
