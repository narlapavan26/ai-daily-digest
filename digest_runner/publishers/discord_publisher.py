"""
digest_runner/publishers/discord_publisher.py
=============================================
Purpose:
  Post digest to Discord via webhook.
  Because Discord has a strict 2000-character limit, we upload the Markdown file 
  as an attachment and send a short summary message.
"""

import httpx
import logging
from pathlib import Path

# pyrefly: ignore [missing-import]
from digest_runner.config.settings import settings

logger = logging.getLogger(__name__)

def publish_to_discord(digest_path: str, total_items: int) -> bool:
    """Publish the digest to Discord via Webhook."""
    webhook_url = settings.discord_webhook_url
    if not webhook_url:
        logger.info("Discord publisher skipped (DISCORD_WEBHOOK_URL not configured).")
        return False

    path = Path(digest_path)
    if not path.exists():
        logger.error(f"Discord publisher failed: file {digest_path} not found.")
        return False

    logger.info("Publishing digest to Discord...")
    
    # 1. Prepare the message
    msg = f"🚀 **AI Daily Digest is ready!**\nFound **{total_items}** high-signal items today. See the attached markdown file for the full brief."

    try:
        # 2. Upload as file attachment to bypass 2000 char limit
        with open(path, "rb") as f:
            files = {
                "file": (path.name, f, "text/markdown")
            }
            payload = {"content": msg}
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(webhook_url, data=payload, files=files)
                response.raise_for_status()
                
        logger.info("Successfully published to Discord!")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to Discord: {e}")
        return False
