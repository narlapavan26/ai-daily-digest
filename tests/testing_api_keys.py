"""
tests/testing_api_keys.py
=========================
Utility script to comprehensively test ALL configured LLM Providers and Publishers.
Run this script to verify your .env configuration before running the main pipeline.

Usage:
    python tests/testing_api_keys.py
"""

import os
import sys
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
import httpx
from openai import OpenAI, APIStatusError

# Add project root to sys.path so we can import digest_runner
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from digest_runner.config.settings import settings
from digest_runner.subgraphs.base import _PROVIDER_CONFIGS

# Fallback models to try if the primary model fails
FALLBACK_MODELS = {
    "GROQ": ["mixtral-8x7b-32768", "gemma2-9b-it", "llama3-8b-8192"],
    "CEREBRAS": ["llama3.1-8b", "llama3.1-70b"],
    "OPENROUTER": ["google/gemini-2.5-flash:free", "meta-llama/llama-3-8b-instruct:free"],
    "GEMINI": ["gemini-1.5-flash", "gemini-2.0-flash"],
    "GITHUB": ["gpt-4o", "Mistral-large"],
    "OLLAMA": ["llama3.1", "qwen2.5"],
    "SAMBANOVA": ["Meta-Llama-3.1-8B-Instruct", "Meta-Llama-3.1-70B-Instruct"]
}

def test_single_model(client, model):
    """Attempts to ping a single model."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly the word 'OK'."}],
        max_tokens=100,
        timeout=15.0
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("API returned an empty (NoneType) response content.")
    return content.strip()

def test_all_llms():
    print("\n" + "=" * 60)
    print("TESTING ALL LLM PROVIDERS")
    print("=" * 60)
    
    results = {}
    
    for provider_enum, config in _PROVIDER_CONFIGS.items():
        provider_name = provider_enum.value.upper()
        key_field = config["key_field"]
        base_url = config["base_url"]
        primary_model = config["model"]
        
        print(f"\n--- {provider_name} ---")
        print(f"  Endpoint: {base_url}")
        
        # Get key from settings or fallback to 'ollama' for local Ollama
        if key_field:
            api_key = getattr(settings, key_field, None)
            if not api_key:
                api_key = os.environ.get(key_field.upper())
        else:
            api_key = "ollama"
            
        if not api_key and provider_name != "OLLAMA":
            print(f"  [SKIP] API key ({key_field}) missing in .env")
            results[provider_name] = {"status": "SKIPPED", "model": "-", "remarks": "No API Key"}
            continue
            
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=1  # Minimal retries so we can fail fast and try fallbacks
        )

        models_to_try = [primary_model] + FALLBACK_MODELS.get(provider_name, [])
        
        success = False
        final_remarks = ""
        successful_model = None
        
        for model in models_to_try:
            print(f"  Testing model: {model}...")
            try:
                reply = test_single_model(client, model)
                print(f"  [SUCCESS] Responded: '{reply}'")
                success = True
                successful_model = model
                final_remarks = "OK"
                break  # Stop trying fallbacks if one succeeds
            except APIStatusError as e:
                # Capture the HTTP status code and specific error message
                status_code = e.status_code
                try:
                    # Try to extract the inner message if it's a JSON error body
                    err_msg = e.response.json().get("error", {}).get("message", str(e))
                except:
                    err_msg = str(e)
                error_str = f"HTTP {status_code}: {err_msg}"
                print(f"  [ERROR] {error_str}")
                final_remarks = error_str
            except Exception as e:
                error_str = f"Error: {e}"
                print(f"  [ERROR] {error_str}")
                final_remarks = error_str
                
        if success:
            results[provider_name] = {"status": "PASSED", "model": successful_model, "remarks": final_remarks}
        else:
            # If we exhausted all fallbacks and failed
            results[provider_name] = {"status": "FAILED", "model": primary_model, "remarks": final_remarks}
            
    return results

def test_discord_webhook():
    print("\n" + "=" * 60)
    print("TESTING PUBLISHER: DISCORD WEBHOOK")
    print("=" * 60)
    webhook_url = settings.discord_webhook_url
    
    if not webhook_url:
        print("  [SKIP] DISCORD_WEBHOOK_URL is not configured in .env")
        return {"status": "SKIPPED", "remarks": "No Webhook URL"}
        
    print(f"  Found Webhook URL: {webhook_url[:40]}...")
    
    payload = {
        "content": "**AI Daily Digest Test:** If you see this, your Discord Webhook in `.env` is configured correctly and working!"
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
        print("  [SUCCESS] Successfully sent test message to Discord!")
        return {"status": "PASSED", "remarks": "OK"}
    except httpx.HTTPStatusError as e:
        err = f"HTTP {e.response.status_code}: {e.response.text}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}
    except Exception as e:
        err = f"Error: {e}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}

def test_telegram_bot():
    print("\n" + "=" * 60)
    print("TESTING PUBLISHER: TELEGRAM BOT")
    print("=" * 60)
    
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    
    missing = []
    if not bot_token: missing.append("TELEGRAM_BOT_TOKEN")
    if not chat_id: missing.append("TELEGRAM_CHAT_ID")
    
    if missing:
        print(f"  [SKIP] Telegram configuration incomplete. Missing: {', '.join(missing)}")
        return {"status": "SKIPPED", "remarks": f"Missing: {','.join(missing)}"}
        
    print(f"  Found Bot Token and Chat ID ({chat_id}). Testing message send...")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "*AI Daily Digest Test:* Your Telegram Bot in `.env` is configured correctly and working!",
        "parse_mode": "Markdown"
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
        print("  [SUCCESS] Successfully sent test message to Telegram!")
        return {"status": "PASSED", "remarks": "OK"}
    except httpx.HTTPStatusError as e:
        err = f"HTTP {e.response.status_code}: {e.response.text}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}
    except Exception as e:
        err = f"Error: {e}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}

def test_email_smtp():
    print("\n" + "=" * 60)
    print("TESTING PUBLISHER: EMAIL SMTP")
    print("=" * 60)
    
    server = settings.smtp_server
    port = settings.smtp_port
    user = settings.smtp_username
    pwd = settings.smtp_password
    to_emails_str = settings.email_to
    from_email = settings.email_from
    
    missing = []
    if not server: missing.append("SMTP_SERVER")
    if not user: missing.append("SMTP_USERNAME")
    if not pwd: missing.append("SMTP_PASSWORD")
    if not to_emails_str: missing.append("EMAIL_TO")
    if not from_email: missing.append("EMAIL_FROM")
    
    if missing:
        print(f"  [SKIP] SMTP configuration incomplete. Missing: {', '.join(missing)}")
        return {"status": "SKIPPED", "remarks": f"Missing: {','.join(missing)}"}
        
    to_emails = [e.strip() for e in to_emails_str.split(",") if e.strip()]
    
    print(f"  Server: {server}:{port}")
    print(f"  Auth User: {user}")
    print(f"  Sending From: {from_email}")
    print(f"  Sending To: {len(to_emails)} recipients ({', '.join(to_emails)})")
    
    try:
        print("  Attempting to connect to SMTP server...")
        with smtplib.SMTP(server, port, timeout=10) as smtp:
            smtp.set_debuglevel(0)
            smtp.starttls()
            print("  Attempting to login...")
            smtp.login(user, pwd)
            print("  [SUCCESS] Login successful! Credentials are valid.")
            
            all_sent = True
            for recipient in to_emails:
                try:
                    print(f"    -> Sending test email to: {recipient}...")
                    test_msg = MIMEText("Your SMTP configuration is working perfectly!", "plain", "utf-8")
                    test_msg["Subject"] = "AI Daily Digest - SMTP Test"
                    test_msg["From"] = from_email
                    test_msg["To"] = recipient
                    
                    smtp.send_message(test_msg)
                    print(f"      [SUCCESS] Sent to {recipient}!")
                except smtplib.SMTPException as e:
                    print(f"      [ERROR] Failed to send to {recipient}: {e}")
                    all_sent = False
                    
        return {"status": "PASSED" if all_sent else "FAILED", "remarks": "OK" if all_sent else "Some emails failed to send"}
    except smtplib.SMTPAuthenticationError as e:
        err = f"SMTP Auth Error: {e.smtp_code} - {e.smtp_error.decode('utf-8')}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}
    except Exception as e:
        err = f"Error: {e}"
        print(f"  [ERROR] {err}")
        return {"status": "FAILED", "remarks": err}

if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("STARTING FULL PIPELINE TEST")
    print("#" * 60)
    
    llm_results = test_all_llms()
    discord_res = test_discord_webhook()
    telegram_res = test_telegram_bot()
    email_res = test_email_smtp()
    
    print("\n" + "=" * 100)
    print("TEST SUMMARY")
    print("=" * 100)
    
    # Define column widths
    w_prov = 12
    w_model = 40
    w_stat = 10
    
    print(f"  {'PROVIDER'.ljust(w_prov)} | {'MODEL/TARGET'.ljust(w_model)} | {'STATUS'.ljust(w_stat)} | REMARKS")
    print("  " + "-" * 98)
    
    for provider, data in llm_results.items():
        status = data["status"]
        model = data["model"]
        remarks = str(data.get("remarks", ""))
        # Truncate remarks if extremely long
        if len(remarks) > 80:
            remarks = remarks[:77] + "..."
        print(f"  {provider.ljust(w_prov)} | {model.ljust(w_model)} | {status.ljust(w_stat)} | {remarks}")
        
    print("  " + "-" * 98)
    
    print(f"  {'DISCORD'.ljust(w_prov)} | {'Webhook'.ljust(w_model)} | {discord_res['status'].ljust(w_stat)} | {discord_res['remarks']}")
    print(f"  {'TELEGRAM'.ljust(w_prov)} | {'Bot API'.ljust(w_model)} | {telegram_res['status'].ljust(w_stat)} | {telegram_res['remarks']}")
    print(f"  {'EMAIL'.ljust(w_prov)} | {'SMTP'.ljust(w_model)} | {email_res['status'].ljust(w_stat)} | {email_res['remarks']}")
    
    print("=" * 100 + "\n")