# Claude Pro Invite Link Hunter & Telegram Notifier

Tool monitoring dan scraping otomatis super-ringan untuk mendeteksi link trial / invite Claude Pro 7 hari yang bocor di ruang publik (Reddit, Telegram public channels, DuckDuckGo) dan langsung mengirimkan notifikasi instan ke chat Telegram via Telegram Bot API.

---

## 📁 Struktur File

- [hunter.py](file:///D:/Kuliah/Web/Claude%20%20Hunter/hunter.py): Engine utama scraper, regex extractor, validasi, dan dispatcher Telegram.
- [requirements.txt](file:///D:/Kuliah/Web/Claude%20%20Hunter/requirements.txt): Minimal dependencies (`httpx`, `python-dotenv`, `selectolax`).
- [.env.example](file:///D:/Kuliah/Web/Claude%20%20Hunter/.env.example): Template konfigurasi environment.
- [.env](file:///D:/Kuliah/Web/Claude%20%20Hunter/.env): File konfigurasi aktif (token bot, chat ID, interval scan).
- [seen_links.txt](file:///D:/Kuliah/Web/Claude%20%20Hunter/seen_links.txt): Database deduplikasi (mencegah notifikasi berulang).
- [hunter.log](file:///D:/Kuliah/Web/Claude%20%20Hunter/hunter.log): Log aktivitas dan riwayat scanning.
- [setup_cron.sh](file:///D:/Kuliah/Web/Claude%20%20Hunter/setup_cron.sh): Script otomasi cron job untuk Linux/VPS.

---

## ⚙️ Cara Konfigurasi Telegram Bot

1. Buka Telegram dan cari **@BotFather**.
2. Kirim `/newbot`, ikuti instruksi, dan salin **Bot Token** yang diberikan.
3. Untuk mendapatkan **Chat ID**:
   - Kirim pesan apa saja ke bot Anda.
   - Buka browser: `https://api.telegram.org/bot<TOKEN_ANDA>/getUpdates`
   - Salin angka `"id"` dari objek `"chat"`.
4. Isi ke file [.env](file:///D:/Kuliah/Web/Claude%20%20Hunter/.env):
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=987654321
   CHECK_INTERVAL_MINUTES=5
   ```

---

## 🚀 Cara Menjalankan

### 1. Mode Uji Coba (Dry-Run)
Menjalankan scan 1 kali tanpa mengirim pesan Telegram dan tanpa menyimpan link:
```bash
python hunter.py --dry-run
```

### 2. Mode Single-Pass (Untuk Cron Job / Linux VPS)
Menjalankan scan 1 kali lalu exit secara bersih:
```bash
python hunter.py
```

### 3. Mode Loop Terus-Menerus (Untuk Windows / Laptop)
Bot akan berjalan terus di background dan otomatis melakukan scan ulang sesuai interval:
```bash
python hunter.py --loop
```
*(Bisa custom interval: `python hunter.py --loop --interval 3` untuk scan per 3 menit)*.

### 4. Mode dengan Validasi HTTP (Opsional)
Menyaring link mati (404 Not Found):
```bash
python hunter.py --validate
```

---

## 🐧 Otomasi di VPS Linux

1. Clone/upload folder ini ke VPS Anda.
2. Jalankan setup cron:
   ```bash
   chmod +x setup_cron.sh
   ./setup_cron.sh
   ```
3. Script otomatis mendeteksi virtualenv dan mendaftarkan cron job sesuai `CHECK_INTERVAL_MINUTES`.

