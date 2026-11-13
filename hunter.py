#!/usr/bin/env python3
"""
BANSOS AI TOKEN & API HUNTER (24/7 Engine)
Scrapes public sources (Reddit, Telegram public channels, AI forums) for:
- Free AI Tokens / Credits (e.g. 10M tokens, $5-$50 vouchers, bansos token)
- Base URLs (OpenAI-compatible endpoints / proxies)
- Free / Leaked API Keys (sk-..., Bearer tokens)
- Claim / Registration Promo Links

Includes built-in HTTP health-check server for Render.com 24/7 hosting.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from selectolax.parser import HTMLParser

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Constants & Paths
SEEN_FILE = os.path.join(BASE_DIR, "seen_bansos.txt")
LOG_FILE = os.path.join(BASE_DIR, "hunter.log")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "2"))

# Target Public Telegram Channels to monitor
DEFAULT_TG_CHANNELS = [
    "freeaipromos",
    "gpt_coupons",
    "DeepSeekAI",
    "OpenRouter",
    "AnthropicClaude",
    "ClaudeAI",
    "llm_promos",
    "chatgpt_free_keys",
    "FreeAI_API",
]
env_channels = os.getenv("TELEGRAM_PUBLIC_CHANNELS", "").strip()
if env_channels:
    TG_CHANNELS = [ch.strip() for ch in env_channels.split(",") if ch.strip()]
else:
    TG_CHANNELS = DEFAULT_TG_CHANNELS

# Regex Patterns for Bansos & API Detection
API_KEY_REGEX = re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b")
BEARER_TOKEN_REGEX = re.compile(r"\bBearer\s+([a-zA-Z0-9_\-]{20,})\b", re.IGNORECASE)
BASE_URL_REGEX = re.compile(
    r"(https?://[a-zA-Z0-9_\-\.]+(?::\d+)?(?:/v1(?:/chat/completions)?|/api/v1)?)",
    re.IGNORECASE,
)
EXPLICIT_BASE_URL_REGEX = re.compile(
    r"(?:base_url|baseUrl|api_base|endpoint)\s*[:=]\s*[\"']?(https?://[a-zA-Z0-9_\-\./:]+)",
    re.IGNORECASE,
)
QUOTA_REGEX = re.compile(
    r"(\b(?:\d+[\.,]?\d*\s*(?:juta|jt|m|k|million|billion|b)\s*(?:token|credit|saldo|tokens)|\$\d+[\.,]?\d*\s*(?:credit|free|voucher|saldo)?)\b)",
    re.IGNORECASE,
)

DURATION_PATTERNS = [
    re.compile(r"(\d+[\s-]*(?:hari|jam|bulan|minggu|days?|hours?|months?|weeks?|hrs?))\s*(?:trial|free|validity|masa aktif|berlaku)?", re.IGNORECASE),
    re.compile(r"(?:valid\s*(?:for|until)?|aktif|durasi|masa\s*aktif|expired|expires\s*(?:in)?|berlaku|trial\s*(?:of)?)\s*[:=]?\s*(\d+\s*(?:hari|jam|bulan|minggu|days?|hours?|months?|weeks?|d|h))", re.IGNORECASE),
    re.compile(r"\b(permanent|no\s*expiry|selamanya|unlimited\s*time)\b", re.IGNORECASE),
]


def format_duration(val: Optional[str]) -> str:
    if not val:
        return "Selama Kuota Masih Ada (Siapa Cepat Dia Dapat)"
    val_lower = val.lower().strip()
    if any(k in val_lower for k in ["perm", "selamanya", "no expiry", "unlimited"]):
        return "Permanen (Tanpa Expired)"
    val_norm = re.sub(r"[\s-]*days?", " Hari", val, flags=re.I)
    val_norm = re.sub(r"[\s-]*hari", " Hari", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*hours?|hrs?", " Jam", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*jam", " Jam", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*months?", " Bulan", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*bulan", " Bulan", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*weeks?", " Minggu", val_norm, flags=re.I)
    val_norm = re.sub(r"[\s-]*minggu", " Minggu", val_norm, flags=re.I)
    return val_norm.strip()


def extract_duration_from_text(text: str) -> str:
    for pat in DURATION_PATTERNS:
        m = pat.search(text)
        if m:
            return format_duration(m.group(1))
    return "Selama Kuota Masih Ada (Siapa Cepat Dia Dapat)"


# Trigger Keywords (To ensure the post is actually about free AI credits / bansos / tokens)
BANSOS_KEYWORDS = [
    "bansos", "free token", "free tokens", "10m token", "10 juta", "free api",
    "free credit", "free credits", "api key", "voucher", "promo code", "claim token",
    "one-api", "new-api", "relay api", "claude pro", "gratis token", "bagi-bagi",
    "giveaway", "free quota", "free tier", "promo"
]

# Known AI Provider Names
KNOWN_PROVIDERS = [
    "SiliconFlow", "DeepSeek", "OpenRouter", "Groq", "Novita AI", "Together AI",
    "Cerebras", "SambaNova", "Mistral", "Cohere", "Fireworks AI", "Cloudflare AI",
    "GitHub Models", "OpenAI", "Anthropic", "Claude", "Kimi", "Moonshot", "Zhipu",
    "GLM-4", "MiniMax", "Qwen", "Alibaba Cloud", "NewAPI", "OneAPI", "Perplexity"
]

# Standard User-Agents
REDDIT_UA = "linux:bansos-hunter:v2.0 (by /u/dev)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Bot Live Statistics (for Render Web Endpoint)
BOT_STATUS = {
    "status": "online",
    "bot_name": "Bansos AI Token & API Hunter",
    "mode": "24/7 Render Continuous Loop",
    "total_scans": 0,
    "last_scan_time": "Never",
    "last_scanned_items": 0,
    "total_bansos_found": 0,
    "check_interval_minutes": CHECK_INTERVAL_MINUTES,
    "start_time": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S WIB"),
}


@dataclass
class BansosItem:
    title: str
    source: str
    platform: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    quota: Optional[str] = None
    duration: Optional[str] = None
    claim_link: Optional[str] = None
    unique_id: str = ""


def log_message(msg: str, to_console: bool = True):
    """Log formatted message to hunter.log and console."""
    wib_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    timestamp_str = wib_now.strftime("%Y-%m-%d %H:%M:%S WIB")
    log_line = f"[{timestamp_str}] {msg}"

    if to_console:
        print(log_line)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        if to_console:
            print(f"Failed to write log file: {e}")


def load_seen_ids() -> Set[str]:
    """Load previously seen Bansos signatures."""
    if not os.path.exists(SEEN_FILE):
        return set()

    seen = set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    seen.add(cleaned)
    except Exception as e:
        log_message(f"[ERROR] Reading seen file failed: {e}")
    return seen


def append_seen_id(unique_id: str):
    """Append a new unique bansos ID."""
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(unique_id + "\n")
    except Exception as e:
        log_message(f"[ERROR] Writing seen file failed: {e}")


def detect_platform(text: str) -> str:
    """Detect AI provider/platform from text."""
    for provider in KNOWN_PROVIDERS:
        if re.search(rf"\b{re.escape(provider)}\b", text, re.IGNORECASE):
            return provider
    return "AI Provider / Relay"


def extract_bansos_from_text(title: str, text: str, source: str, link_url: str = "") -> Optional[BansosItem]:
    """
    Intelligently parses text snippet to check if it contains AI Bansos / Free Tokens / API Key.
    """
    combined = f"{title} {text} {link_url}"
    lower_combined = combined.lower()

    # Must contain at least one bansos keyword or explicit sk- key
    has_keyword = any(kw in lower_combined for kw in BANSOS_KEYWORDS)
    has_api_key = bool(API_KEY_REGEX.search(combined) or BEARER_TOKEN_REGEX.search(combined))

    if not (has_keyword or has_api_key):
        return None

    # 1. Extract API Key
    api_key = None
    sk_match = API_KEY_REGEX.search(combined)
    if sk_match:
        api_key = sk_match.group(1)
    else:
        bearer_match = BEARER_TOKEN_REGEX.search(combined)
        if bearer_match:
            api_key = bearer_match.group(1)

    # 2. Extract Base URL
    base_url = None
    explicit_match = EXPLICIT_BASE_URL_REGEX.search(combined)
    if explicit_match:
        base_url = explicit_match.group(1).rstrip("/\"',")
    else:
        for u in BASE_URL_REGEX.findall(combined):
            # Only consider as base_url if it looks like an API endpoint (has /v1 or api in host)
            if "/v1" in u or "api." in u:
                base_url = u.rstrip("/\"',")
                break

    # 3. Extract Quota / Benefit info
    quota = None
    quota_match = QUOTA_REGEX.search(combined)
    if quota_match:
        quota = quota_match.group(1).strip()
    elif "10m" in lower_combined or "10 juta" in lower_combined:
        quota = "10 Juta Token"
    elif "free" in lower_combined and "token" in lower_combined:
        quota = "Free Tokens / Credits"

    # 4. Extract Claim / Referral / Promo link if present
    claim_link = None
    urls = re.findall(r"https?://[^\s<>\"']+", combined)
    for u in urls:
        # Ignore reddit / telegram internal navigation links
        if "reddit.com" in u and "/r/" in u and "comments" not in u:
            continue
        if "t.me/" in u and not any(k in u.lower() for k in ["bot", "claim", "join", "promo"]):
            continue
        if any(term in u.lower() for term in ["claim", "promo", "invite", "referral", "/i/", "register", "signup"]):
            claim_link = u
            break

    # Fallback claim_link to post URL if available
    if not claim_link and link_url:
        claim_link = link_url

    # 5. Detect Platform
    platform = detect_platform(combined)

    # 6. Extract Duration / Validity (Berapa hari / jam / bulan / permanen)
    duration = extract_duration_from_text(combined)

    # Strict Validation: Must be genuine Bansos / Free Token / API Key
    is_real_bansos = False
    if api_key:
        is_real_bansos = True
    elif base_url and (claim_link or quota):
        is_real_bansos = True
    elif quota and (claim_link or any(k in lower_combined for k in ["bansos", "promo", "voucher", "free token", "gratis", "claim", "klaim"])):
        is_real_bansos = True
    elif any(k in lower_combined for k in ["bansos", "bagi-bagi", "free api key", "free credits", "10m token", "10 juta token"]):
        is_real_bansos = True

    if not is_real_bansos:
        return None

    # Generate Unique ID for Deduplication
    if api_key:
        uid = f"key:{api_key}"
    elif claim_link and any(k in claim_link.lower() for k in ["claim", "promo", "/i/", "invite"]):
        uid = f"claim:{claim_link}"
    else:
        content_hash = hashlib.md5(f"{platform}_{title}_{quota}_{base_url}".encode("utf-8")).hexdigest()[:12]
        uid = f"post:{content_hash}"

    return BansosItem(
        title=title[:120].strip(),
        source=source,
        platform=platform,
        base_url=base_url,
        api_key=api_key,
        quota=quota,
        duration=duration,
        claim_link=claim_link,
        unique_id=uid,
    )


# ==============================================================================
# SOURCE SCRAPERS
# ==============================================================================

def scrape_reddit(client: httpx.Client) -> List[BansosItem]:
    """Scrape Reddit (LocalLLaMA, OpenAI, ChatGPT, ArtificialIntelligence) for AI bansos."""
    results = []
    headers = {"User-Agent": REDDIT_UA}

    reddit_targets = [
        ("Reddit r/LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/new.json?limit=25", "https://www.reddit.com/r/LocalLLaMA/new.rss"),
        ("Reddit r/OpenAI", "https://www.reddit.com/r/OpenAI/new.json?limit=25", "https://www.reddit.com/r/OpenAI/new.rss"),
        ("Reddit Search Bansos", "https://www.reddit.com/search.json?q=free+tokens+OR+free+api+key+OR+siliconflow+OR+deepseek+api+OR+10M+tokens&sort=new&limit=25", "https://www.reddit.com/search.rss?q=free+tokens+OR+free+api+key+OR+siliconflow+OR+deepseek+api+OR+10M+tokens&sort=new"),
    ]

    for label, json_url, rss_url in reddit_targets:
        try:
            resp = client.get(json_url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", {}).get("children", []):
                    post = item.get("data", {})
                    title = post.get("title", "")
                    selftext = post.get("selftext", "")
                    url = post.get("url", "")
                    permalink = f"https://reddit.com{post.get('permalink', '')}"

                    item_obj = extract_bansos_from_text(title, selftext, label, link_url=permalink or url)
                    if item_obj:
                        results.append(item_obj)
            else:
                # Fallback to RSS
                resp_rss = client.get(rss_url, headers={"User-Agent": BROWSER_UA}, timeout=10.0)
                if resp_rss.status_code == 200:
                    tree = HTMLParser(resp_rss.text)
                    for entry in tree.css("entry"):
                        title_node = entry.css_first("title")
                        content_node = entry.css_first("content")
                        link_node = entry.css_first("link")

                        title = title_node.text() if title_node else ""
                        content = content_node.text() if content_node else ""
                        url = link_node.attributes.get("href", "") if link_node else ""

                        item_obj = extract_bansos_from_text(title, content, label, link_url=url)
                        if item_obj:
                            results.append(item_obj)
        except Exception as e:
            log_message(f"[{label}] Error fetching: {e}")

    return results


def scrape_telegram_channels(client: httpx.Client, channels: List[str]) -> List[BansosItem]:
    """Scrape Telegram public web preview channels for shared AI keys / bansos."""
    results = []
    headers = {"User-Agent": BROWSER_UA}

    for channel in channels:
        label = f"Telegram @{channel}"
        url = f"https://t.me/s/{channel}"
        try:
            resp = client.get(url, headers=headers, follow_redirects=True, timeout=10.0)
            if resp.status_code == 200:
                tree = HTMLParser(resp.text)
                message_nodes = tree.css(".tgme_widget_message")
                for node in message_nodes:
                    text_node = node.css_first(".tgme_widget_message_text")
                    if not text_node:
                        continue
                    text = text_node.text(deep=True)

                    # Extract message link
                    post_link = ""
                    date_node = node.css_first(".tgme_widget_message_date")
                    if date_node:
                        post_link = date_node.attributes.get("href", "")

                    item_obj = extract_bansos_from_text(
                        title=f"Promo Post in @{channel}",
                        text=text,
                        source=label,
                        link_url=post_link or url,
                    )
                    if item_obj:
                        results.append(item_obj)
        except Exception as e:
            log_message(f"[{label}] Error fetching Telegram channel: {e}")

    return results


def scrape_web_search(client: httpx.Client) -> List[BansosItem]:
    """Search dorking for free API keys & base URLs."""
    results = []
    label = "Web Search"
    query = '("base_url" OR "10M tokens") ("sk-" OR "free api key") ("siliconflow" OR "deepseek" OR "openrouter")'
    headers = {"User-Agent": BROWSER_UA}

    try:
        resp = client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=headers,
            follow_redirects=True,
            timeout=10.0,
        )
        if resp.status_code == 200:
            tree = HTMLParser(resp.text)
            for result_node in tree.css(".result"):
                title_node = result_node.css_first(".result__title")
                snippet_node = result_node.css_first(".result__snippet")
                url_node = result_node.css_first(".result__url")

                title = title_node.text(deep=True) if title_node else ""
                snippet = snippet_node.text(deep=True) if snippet_node else ""
                url = url_node.text(deep=True) if url_node else ""

                item_obj = extract_bansos_from_text(title, snippet, label, link_url=url)
                if item_obj:
                    results.append(item_obj)
    except Exception as e:
        log_message(f"[{label}] Search attempt skipped ({e.__class__.__name__})")

    return results


# ==============================================================================
# TELEGRAM DISPATCHER
# ==============================================================================

def is_telegram_configured() -> bool:
    """Check if bot token and chat id are properly set."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    if "isi_angka" in TELEGRAM_CHAT_ID.lower() or "your_" in TELEGRAM_CHAT_ID.lower():
        return False
    return True


def send_telegram_bansos(client: httpx.Client, item: BansosItem) -> bool:
    """Send formatted Bansos alert to Telegram."""
    if not is_telegram_configured():
        log_message(f"[TELEGRAM SKIP] Bot token/chat_id not configured. Bansos: {item.title}")
        return False

    wib_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    time_str = wib_now.strftime("%Y-%m-%d %H:%M:%S WIB")

    msg_lines = [
        "🎁 <b>[BANSOS AI TOKEN DETECTED!]</b> 🎁\n",
        f"🏷 <b>Platform:</b> {item.platform}",
    ]

    if item.quota:
        msg_lines.append(f"💰 <b>Kuota / Benefit:</b> {item.quota}")

    if item.duration:
        msg_lines.append(f"⏳ <b>Masa Aktif / Durasi:</b> {item.duration}")

    if item.base_url:
        msg_lines.append(f"🌐 <b>Base URL:</b> <code>{item.base_url}</code>")

    if item.api_key:
        msg_lines.append(f"🔑 <b>API Key:</b> <code>{item.api_key}</code>")
    else:
        msg_lines.append("🔑 <b>API Key:</b> Klaim via link pendaftaran di bawah")

    if item.claim_link:
        msg_lines.append(f"🔗 <b>Link Klaim / Post:</b> <a href=\"{item.claim_link}\">Buka Link Bansos</a>")

    msg_lines.append(f"\n📍 <b>Sumber:</b> {item.source}")
    msg_lines.append(f"⏰ <b>Waktu:</b> {time_str}")

    message_text = "\n".join(msg_lines)

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resp = client.post(api_url, json=payload, timeout=10.0)
        if resp.status_code == 200 and resp.json().get("ok"):
            log_message(f"[TELEGRAM SENT] Successfully alerted {item.platform} - {item.title}")
            return True
        else:
            log_message(f"[TELEGRAM ERROR] API returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        log_message(f"[TELEGRAM ERROR] Dispatch failed: {e}")
        return False


# ==============================================================================
# MAIN SCAN ENGINE
# ==============================================================================

def run_scan(dry_run: bool = False) -> int:
    """Execute 1 full pass scanning for Bansos AI Tokens & API Keys."""
    start_time = time.time()
    log_message(f"=== Starting Bansos Scan Pass (dry_run={dry_run}) ===")

    seen_ids = load_seen_ids()
    log_message(f"Loaded {len(seen_ids)} previously seen bansos items")

    all_items: List[BansosItem] = []

    transport = httpx.HTTPTransport(retries=1, verify=False)
    with httpx.Client(transport=transport, timeout=15.0) as client:
        # 1. Scrape Reddit
        reddit_items = scrape_reddit(client)
        all_items.extend(reddit_items)

        # 2. Scrape Telegram Public Channels
        tg_items = scrape_telegram_channels(client, TG_CHANNELS)
        all_items.extend(tg_items)

        # 3. Scrape Web Search
        search_items = scrape_web_search(client)
        all_items.extend(search_items)

        # Deduplicate within current run
        unique_new_items: Dict[str, BansosItem] = {}
        for item in all_items:
            if item.unique_id and item.unique_id not in seen_ids:
                unique_new_items[item.unique_id] = item

        total_scanned = len(all_items)
        new_count = len(unique_new_items)
        log_message(f"Discovered: {total_scanned} candidate posts | New unseen Bansos: {new_count}")

        dispatched_count = 0
        for uid, item in unique_new_items.items():
            if dry_run:
                log_message(f"[DRY-RUN MATCH] Would alert Telegram for {item.platform}: {item.title} (Key: {item.api_key}, URL: {item.base_url})")
                dispatched_count += 1
            else:
                sent = send_telegram_bansos(client, item)
                append_seen_id(uid)
                dispatched_count += 1

    elapsed = time.time() - start_time
    wib_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    BOT_STATUS["total_scans"] += 1
    BOT_STATUS["last_scan_time"] = wib_now.strftime("%Y-%m-%d %H:%M:%S WIB")
    BOT_STATUS["last_scanned_items"] = total_scanned
    BOT_STATUS["total_bansos_found"] += dispatched_count

    log_message(f"=== Scan Finished in {elapsed:.2f}s. Processed {dispatched_count} new alerts. ===\n")
    return dispatched_count


# ==============================================================================
# RENDER 24/7 WEB HEALTH-CHECK SERVER
# ==============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler responding to health checks for Render.com & UptimeRobot."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = json.dumps(BOT_STATUS, indent=2)
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, format, *args):
        # Silence access logs so hunter.log stays clean
        pass


def start_server_mode(port: int, interval_minutes: int, dry_run: bool):
    """
    Start lightweight HTTP health-check server and background hunter loop.
    Designed for Render.com free tier paired with UptimeRobot (24/7 non-stop).
    """
    interval_sec = max(1, interval_minutes) * 60
    BOT_STATUS["check_interval_minutes"] = interval_minutes

    def hunting_worker():
        log_message(f"Background Bansos Hunter worker started! Scanning every {interval_minutes} minute(s).")
        time.sleep(3)  # Brief wait so web server binds first
        while True:
            try:
                run_scan(dry_run=dry_run)
            except Exception as e:
                log_message(f"[BACKGROUND WORKER ERROR] {e}")
            time.sleep(interval_sec)

    worker_thread = threading.Thread(target=hunting_worker, daemon=True)
    worker_thread.start()

    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    log_message(f"Web Health Server running on http://0.0.0.0:{port} (Ready for Render & UptimeRobot 24/7)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log_message("Web server stopped by user. Exiting.")
        httpd.server_close()
        sys.exit(0)


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bansos AI Token & API Hunter (Reddit, Telegram, Web 24/7 Notifier)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scan without writing to seen_bansos.txt or sending live telegram messages",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a test Bansos notification to verify Telegram bot credentials",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop sleeping CHECK_INTERVAL_MINUTES (useful for local dev)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start HTTP healthcheck web server and background hunting loop (ideal for Render.com)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8080")),
        help="Port for HTTP web server (default: from PORT env or 8080)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("CHECK_INTERVAL_MINUTES", "2")),
        help="Interval in minutes when running in loop or server mode (default: from .env or 2)",
    )

    args = parser.parse_args()

    # Check if running in Web / Cloud host mode (Render, Koyeb, etc.)
    env_port = os.getenv("PORT")
    if args.serve or env_port:
        port = args.port if args.serve else int(env_port)
        start_server_mode(
            port=port,
            interval_minutes=args.interval,
            dry_run=args.dry_run,
        )
        return

    if args.test_telegram:
        log_message("Sending test Bansos notification to Telegram...")
        transport = httpx.HTTPTransport(retries=1, verify=False)
        with httpx.Client(transport=transport, timeout=10.0) as client:
            sample_item = BansosItem(
                title="Bansos 10 Juta Token SiliconFlow (System Test)",
                source="System Test",
                platform="SiliconFlow",
                base_url="https://api.siliconflow.cn/v1",
                api_key="sk-sample1234567890abcdef1234567890abcdef",
                quota="10 Juta Token Gratis",
                duration="30 Hari (Promo Terbatas)",
                claim_link="https://cloud.siliconflow.cn/i/sample-claim-link",
                unique_id="test-bansos-uid",
            )
            success = send_telegram_bansos(client, sample_item)
            if success:
                log_message("[SUCCESS] Pesan tes Bansos berhasil dikirim ke akun Telegram Anda! Cek HP Anda.")
            else:
                log_message("[FAILED] Gagal kirim pesan. Pastikan TELEGRAM_BOT_TOKEN valid dan Anda sudah klik START di bot Telegram.")
        return

    if args.loop:
        interval_sec = max(1, args.interval) * 60
        log_message(f"Starting Bansos Hunter in LOOP mode every {args.interval} minutes. Press Ctrl+C to stop.")
        try:
            while True:
                run_scan(dry_run=args.dry_run)
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            log_message("Loop stopped by user. Exiting cleanly.")
            sys.exit(0)
    else:
        # Single-run cron execution
        run_scan(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
