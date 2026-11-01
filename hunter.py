#!/usr/bin/env python3
"""
TASK DIRECTIVE: CLAUDE PRO INVITE LINK HUNTER & TELEGRAM NOTIFIER
Core Engine for periodic scraping, regex extraction, deduplication, and Telegram alert dispatch.
"""

import argparse
import datetime
import os
import re
import sys
import time
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from selectolax.parser import HTMLParser

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Constants & Paths
SEEN_LINKS_FILE = os.path.join(BASE_DIR, "seen_links.txt")
LOG_FILE = os.path.join(BASE_DIR, "hunter.log")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

# Default public Telegram channels to monitor for promo/invite shares
DEFAULT_TG_CHANNELS = [
    "AnthropicClaude",
    "ClaudeAI",
    "freeaipromos",
    "gpt_coupons",
]
env_channels = os.getenv("TELEGRAM_PUBLIC_CHANNELS", "").strip()
if env_channels:
    TG_CHANNELS = [ch.strip() for ch in env_channels.split(",") if ch.strip()]
else:
    TG_CHANNELS = DEFAULT_TG_CHANNELS

# Regex pattern for Claude invite/claim/promo/referral links
CLAUDE_LINK_REGEX = re.compile(
    r"https?://(?:www\.)?claude\.ai/(?:invite|claim|promo|referral)/[a-zA-Z0-9_\-]+",
    re.IGNORECASE,
)

# Standard User-Agents
REDDIT_UA = "linux:claude-hunter:v1.0 (by /u/dev)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def log_message(msg: str, to_console: bool = True):
    """Log formatted message to both hunter.log and console."""
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


def load_seen_links() -> Set[str]:
    """Load previously seen links from seen_links.txt."""
    if not os.path.exists(SEEN_LINKS_FILE):
        return set()

    seen = set()
    try:
        with open(SEEN_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    seen.add(cleaned)
    except Exception as e:
        log_message(f"[ERROR] Reading seen_links.txt failed: {e}")
    return seen


def append_seen_link(link: str):
    """Append a new unique link to seen_links.txt."""
    try:
        with open(SEEN_LINKS_FILE, "a", encoding="utf-8") as f:
            f.write(link + "\n")
    except Exception as e:
        log_message(f"[ERROR] Writing to seen_links.txt failed: {e}")


def normalize_link(link: str) -> str:
    """Normalize link by removing query parameters, fragments, and trailing slashes."""
    parsed = urlparse(link)
    clean_path = parsed.path.rstrip("/")
    return f"https://claude.ai{clean_path}"


def extract_links_from_text(text: str) -> List[str]:
    """Extract and normalize all Claude invite/claim links from raw text."""
    if not text:
        return []
    matches = CLAUDE_LINK_REGEX.findall(text)
    return [normalize_link(m) for m in matches]


# ==============================================================================
# SOURCE SCRAPERS
# ==============================================================================

def scrape_reddit(client: httpx.Client) -> List[Tuple[str, str]]:
    """
    Scrape Reddit for Claude invite links.
    Tries JSON endpoint first; falls back smoothly to RSS if 403/429 is encountered.
    """
    found_links = []
    headers = {"User-Agent": REDDIT_UA}

    reddit_endpoints = [
        ("Reddit r/ClaudeAI", "https://www.reddit.com/r/ClaudeAI/new.json?limit=25", "https://www.reddit.com/r/ClaudeAI/new.rss"),
        ("Reddit Search", "https://www.reddit.com/search.json?q=claude+invite+OR+claude+pro+trial&sort=new&limit=25", "https://www.reddit.com/search.rss?q=claude+invite+OR+claude+pro+trial&sort=new"),
    ]

    for label, json_url, rss_url in reddit_endpoints:
        extracted = []
        try:
            # 1. Try JSON API
            resp = client.get(json_url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for item in children:
                    post = item.get("data", {})
                    title = post.get("title", "")
                    selftext = post.get("selftext", "")
                    url = post.get("url", "")
                    raw_content = f"{title} {selftext} {url}"
                    for link in extract_links_from_text(raw_content):
                        extracted.append(link)
            else:
                # 2. Fallback to RSS Feed if JSON is blocked
                resp_rss = client.get(rss_url, headers={"User-Agent": BROWSER_UA}, timeout=10.0)
                if resp_rss.status_code == 200:
                    for link in extract_links_from_text(resp_rss.text):
                        extracted.append(link)
                else:
                    log_message(f"[{label}] Both JSON ({resp.status_code}) and RSS ({resp_rss.status_code}) returned non-200.")
        except Exception as e:
            log_message(f"[{label}] Error fetching: {e}")

        for link in set(extracted):
            found_links.append((link, label))

    return found_links


def scrape_telegram_web(client: httpx.Client, channels: List[str]) -> List[Tuple[str, str]]:
    """
    Scrape Telegram public preview channels (https://t.me/s/<channel>).
    Extracts text using selectolax HTMLParser.
    """
    found_links = []
    headers = {"User-Agent": BROWSER_UA}

    for channel in channels:
        url = f"https://t.me/s/{channel}"
        label = f"Telegram @{channel}"
        try:
            resp = client.get(url, headers=headers, follow_redirects=True, timeout=10.0)
            if resp.status_code == 200:
                tree = HTMLParser(resp.text)
                # Messages text preview in Telegram web
                msg_nodes = tree.css(".tgme_widget_message_text")
                channel_text = " ".join([node.text(deep=True) for node in msg_nodes])
                
                # Also check all <a> href attributes
                links_in_attrs = []
                for a_tag in tree.css("a"):
                    href = a_tag.attributes.get("href", "")
                    if href:
                        links_in_attrs.append(href)
                
                combined_content = channel_text + " " + " ".join(links_in_attrs)
                for link in set(extract_links_from_text(combined_content)):
                    found_links.append((link, label))
            else:
                log_message(f"[{label}] Status code {resp.status_code}")
        except Exception as e:
            log_message(f"[{label}] Error fetching preview: {e}")

    return found_links


def scrape_search_duckduckgo(client: httpx.Client) -> List[Tuple[str, str]]:
    """
    Lightweight dorking search query via DuckDuckGo HTML/Lite.
    Gracefully handles SSL/network blocks.
    """
    found_links = []
    label = "Search (DuckDuckGo)"
    query = '"claude.ai/invite/" OR "claude.ai/claim/"'
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    urls_to_try = [
        ("https://html.duckduckgo.com/html/", {"q": query}),
        ("https://lite.duckduckgo.com/lite/", {"q": query}),
    ]

    for search_url, form_data in urls_to_try:
        try:
            resp = client.post(
                search_url,
                data=form_data,
                headers=headers,
                follow_redirects=True,
                timeout=10.0,
            )
            if resp.status_code == 200:
                tree = HTMLParser(resp.text)
                # Check text snippets and anchor targets
                content_snippets = []
                for node in tree.css(".result__snippet, .result__url, a"):
                    txt = node.text(deep=True)
                    href = node.attributes.get("href", "")
                    content_snippets.append(f"{txt} {href}")

                combined = " ".join(content_snippets)
                for link in set(extract_links_from_text(combined)):
                    found_links.append((link, label))
                if found_links:
                    break
        except Exception as e:
            # DuckDuckGo might be blocked by local ISP or throw SSL error
            log_message(f"[{label}] Search attempt failed ({e.__class__.__name__}). Skipping search source.")
            break

    return found_links


# ==============================================================================
# LINK VALIDATOR
# ==============================================================================

def validate_link(client: httpx.Client, url: str) -> bool:
    """
    Fast HTTP HEAD/GET to check if link is not an outright 404 dead link.
    Notice: Cloudflare 403 or redirects are NOT treated as dead links!
    """
    try:
        resp = client.head(url, headers={"User-Agent": BROWSER_UA}, follow_redirects=True, timeout=5.0)
        # 404 or 410 Gone means dead link
        if resp.status_code in (404, 410):
            return False
        return True
    except Exception:
        # If head fails or times out, do GET fallback
        try:
            resp = client.get(url, headers={"User-Agent": BROWSER_UA}, follow_redirects=True, timeout=5.0)
            if resp.status_code in (404, 410):
                return False
            return True
        except Exception:
            # Assume potentially valid on network/timeout error so we don't drop real invites
            return True


# ==============================================================================
# TELEGRAM DISPATCHER
# ==============================================================================

def is_telegram_configured() -> bool:
    """Check if bot token and chat id are properly set and not placeholders."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    if "isi_angka" in TELEGRAM_CHAT_ID.lower() or "your_" in TELEGRAM_CHAT_ID.lower():
        return False
    return True


def send_telegram_alert(client: httpx.Client, link: str, source: str) -> bool:
    """
    Dispatch formatted Telegram alert via Bot API.
    """
    if not is_telegram_configured():
        log_message(f"[TELEGRAM SKIP] Bot token or chat_id is missing or placeholder. Link found: {link}")
        return False

    wib_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    time_str = wib_now.strftime("%Y-%m-%d %H:%M:%S WIB")

    message_text = (
        "🚨 <b>[CLAUDE PRO INVITE DETECTED]</b> 🚨\n\n"
        f"🔗 <b>Link:</b> {link}\n"
        f"📍 <b>Source:</b> {source}\n"
        f"⏰ <b>Time:</b> {time_str}"
    )

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
            log_message(f"[TELEGRAM SENT] Successfully alerted {link} from {source}")
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

def run_scan(dry_run: bool = False, validate: bool = False) -> int:
    """
    Execute a single pass scan across all sources:
    1. Scrapes Reddit, Telegram channels, and Search.
    2. Filters seen links from seen_links.txt.
    3. Validates live status (optional).
    4. Sends Telegram notification.
    5. Appends new links to seen_links.txt.
    """
    start_time = time.time()
    log_message(f"=== Starting Scan Pass (dry_run={dry_run}, validate={validate}) ===")

    seen_links = load_seen_links()
    log_message(f"Loaded {len(seen_links)} known links from seen_links.txt")

    discovered: Dict[str, str] = {}  # link -> source

    # Configure resilient HTTP client
    transport = httpx.HTTPTransport(retries=1, verify=False)
    with httpx.Client(transport=transport, timeout=15.0) as client:
        # 1. Scrape Reddit
        reddit_results = scrape_reddit(client)
        for link, src in reddit_results:
            if link not in discovered:
                discovered[link] = src

        # 2. Scrape Telegram Public Web Channels
        tg_results = scrape_telegram_web(client, TG_CHANNELS)
        for link, src in tg_results:
            if link not in discovered:
                discovered[link] = src

        # 3. Scrape DuckDuckGo Search
        search_results = scrape_search_duckduckgo(client)
        for link, src in search_results:
            if link not in discovered:
                discovered[link] = src

        total_scanned = len(discovered)
        new_links = [
            (link, src) for link, src in discovered.items()
            if link not in seen_links
        ]

        log_message(f"Discovered: {total_scanned} total links on public sources | New unseen links: {len(new_links)}")

        dispatched_count = 0
        for link, source in new_links:
            # Optional Validation
            if validate:
                log_message(f"Validating {link} ...")
                if not validate_link(client, link):
                    log_message(f"[DEAD LINK SKIP] Link {link} returned 404/expired.")
                    if not dry_run:
                        append_seen_link(link)
                    continue

            if dry_run:
                log_message(f"[DRY-RUN MATCH] Would alert Telegram for: {link} (Source: {source})")
                dispatched_count += 1
            else:
                sent = send_telegram_alert(client, link, source)
                append_seen_link(link)
                dispatched_count += 1

    elapsed = time.time() - start_time
    log_message(f"=== Scan Finished in {elapsed:.2f}s. Processed {dispatched_count} new alerts. ===\n")
    return dispatched_count


def main():
    parser = argparse.ArgumentParser(
        description="Claude Pro Invite Link Hunter & Telegram Notifier"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scan without writing to seen_links.txt or sending live telegram messages",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a test notification to your Telegram to verify bot credentials",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Perform HTTP HEAD check to filter out 404 dead links",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop sleeping CHECK_INTERVAL_MINUTES (useful for Windows / local dev)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL_MINUTES,
        help="Interval in minutes when running in --loop mode (default: from .env or 30)",
    )

    args = parser.parse_args()

    if args.test_telegram:
        log_message("Sending test notification to Telegram...")
        transport = httpx.HTTPTransport(retries=1, verify=False)
        with httpx.Client(transport=transport, timeout=10.0) as client:
            success = send_telegram_alert(
                client,
                link="https://claude.ai/claim/test-notification-success",
                source="System Test",
            )
            if success:
                log_message("[SUCCESS] Pesan tes berhasil dikirim ke akun Telegram Anda! Cek HP Anda.")
            else:
                log_message("[FAILED] Gagal kirim pesan. Pastikan TELEGRAM_BOT_TOKEN valid dan Anda sudah klik START di bot Telegram.")
        return

    if args.loop:
        interval_sec = max(1, args.interval) * 60
        log_message(f"Starting hunter in LOOP mode every {args.interval} minutes. Press Ctrl+C to stop.")
        try:
            while True:
                run_scan(dry_run=args.dry_run, validate=args.validate)
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            log_message("Loop stopped by user. Exiting cleanly.")
            sys.exit(0)
    else:
        # Single-run cron execution
        run_scan(dry_run=args.dry_run, validate=args.validate)


if __name__ == "__main__":
    main()
