# Claude Pro Invite Link Hunter & Telegram Notifier

Tool monitoring dan scraping otomatis super-ringan untuk mendeteksi link trial / invite Claude Pro 7 hari yang bocor di ruang publik (Reddit, Telegram public channels, DuckDuckGo) dan langsung mengirimkan notifikasi instan ke chat Telegram via Telegram Bot API.

---

## 📁 Struktur File

- `hunter.py`: Engine utama scraper, regex extractor, HTTP health-check server, dan Telegram dispatcher.
- `requirements.txt`: Minimal dependencies (`httpx`, `python-dotenv`, `selectolax`).
- `render.yaml`: Blueprint konfigurasi 1-klik untuk hosting di **Render.com**.
- `.github/workflows/hunter.yml`: Otomasi background runner via **GitHub Actions**.
- `seen_links.txt`: Database deduplikasi (mencegah notifikasi ganda).
- `setup_cron.sh`: Script instalasi crontab di VPS Linux.

---

## 🌐 Cara Deploy ke Render.com (Aktif 24 Jam Non-Stop)

1. Buka [dashboard.render.com](https://dashboard.render.com) lalu Login dengan akun GitHub Anda.
2. Klik tombol **New +** ➔ pilih **Web Service**.
3. Hubungkan ke repository ini: **`Arterouss/Agent-Hu`**.
4. Isi konfigurasi:
   - **Name:** `claude-hunter-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python hunter.py --serve --interval 2`
   - **Instance Type:** `Free`
5. Di bagian **Environment Variables**, tambahkan:
   - `TELEGRAM_BOT_TOKEN` : Token bot Telegram Anda
   - `TELEGRAM_CHAT_ID` : ID chat Telegram Anda (`1117401017`)
   - `CHECK_INTERVAL_MINUTES` : `2`
6. Klik **Deploy Web Service**.

### ⏰ Supaya Render Tidak Tidur (Always Awake):
1. Buka [uptimerobot.com](https://uptimerobot.com) (gratis).
2. Buat monitor baru:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `Claude Hunter Bot`
   - **URL:** Masukkan URL web Render Anda (contoh: `https://claude-hunter-bot.onrender.com/`)
   - **Monitoring Interval:** Setiap 5 menit.
3. Bot Anda sekarang **resmi online 24 jam non-stop** dan melakukan scan setiap 2 menit sekali!
