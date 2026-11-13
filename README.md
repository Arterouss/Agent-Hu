# 🎁 Bansos AI Token & API Hunter (24/7 Telegram Alert)

Tool pemantau dan scraping otomatis super-ringan untuk mendeteksi **Bansos Token AI, Free API Credits (misal 10M / 10 Juta Token, Voucher Saldo), Base URL endpoint proxy/relay, dan API Key gratis (sk-...)** yang dibagikan di Reddit, channel Telegram publik, dan forum AI.

Notifikasi instan langsung dikirim ke HP via **Telegram Bot API**.

---

## ✨ Fitur Utama

- 🔍 **Deteksi Bansos AI Otomatis**:
  - Kuota Token / Credit gratis (e.g. `10 Juta Token`, `10M tokens`, `$5 - $50 Free Credit`).
  - **Masa Aktif / Durasi Bansos** (e.g. `30 Hari`, `7 Hari`, `24 Jam`, `Permanen`).
  - **Base URL Otomatis (1-Tap Copy)**: Auto-fill endpoint resmi jika tidak tertulis di postingan.
  - **API Key Otomatis (1-Tap Copy)**: Key berformat `sk-...` langsung siap disalin dari chat Telegram tanpa buka web!
  - **Link Registrasi Promo / Voucher Klaim**.
- 🌐 **Web Health Server Terintegrasi (`--serve`)**:
  - Didesain khusus untuk hosting gratis di **Render.com** (tersedia endpoint `/` status live bot).
  - Cukup sambungkan ke **UptimeRobot** agar bot aktif **24 jam non-stop** tanpa sleep!
- 🛡️ **Anti-Duplikasi Cerdas (`seen_bansos.txt`)**:
  - Mengingat key / link klaim yang sudah pernah dikirim agar tidak terjadi spam berulang.
- 🐧 **Cadangan Otomasi GitHub Actions**:
  - Tetap bisa berjalan terjadwal tiap 5 menit jika tidak memakai Render.

---

## 📱 Contoh Format Pesan Notifikasi Telegram (Tinggal Salin 1-Tap)

```text
🎁 [BANSOS AI TOKEN DETECTED!] 🎁

🏷 Platform: SiliconFlow
💰 Kuota / Benefit: 10 Juta Token Gratis
⏳ Masa Aktif / Durasi: 30 Hari (Promo Terbatas)

🌐 Base URL (Tap untuk Salin):
https://api.siliconflow.cn/v1

🔑 API Key (Tap untuk Salin):
sk-abcdef1234567890abcdef...

🔗 Link Klaim / Post: https://cloud.siliconflow.cn/i/promo123
📍 Sumber: Telegram @freeaipromos
⏰ Waktu: 2026-11-13 12:00:00 WIB
```

---

## 🚀 Cara Pasang 24 Jam Non-Stop di Render.com

1. Buka [dashboard.render.com](https://dashboard.render.com) lalu Login dengan akun GitHub Anda.
2. Klik tombol **New +** ➔ pilih **Web Service**.
3. Sambungkan ke repository Anda: **`Arterouss/Agent-Hu`**.
4. Masukkan konfigurasi:
   - **Name:** `bansos-ai-hunter`
   - **Region:** `Singapore`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python hunter.py --serve --interval 2`
   - **Instance Type:** `Free ($0/mo)`
5. Di bagian **Environment Variables**, tambahkan:
   - `TELEGRAM_BOT_TOKEN` : `9163201803:AAGbDlQHKNz-kTVmsnjKl0CZu7cE1DPPI7g`
   - `TELEGRAM_CHAT_ID` : `1117401017`
   - `CHECK_INTERVAL_MINUTES` : `2`
6. Klik **Deploy Web Service**.

### ⏰ Supaya Render Tidak Pernah Tidur (Always Awake 24/7):
1. Buka [uptimerobot.com](https://uptimerobot.com) (gratis).
2. Buat monitor baru:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `Bansos AI Hunter`
   - **URL:** Masukkan URL web Render Anda (misal: `https://bansos-ai-hunter.onrender.com/`)
   - **Monitoring Interval:** Setiap 5 menit.
3. Bot sekarang **resmi aktif 24 jam non-stop** dan memindai setiap 2 menit sekali!

---

## 💻 Cara Menjalankan di Lokal (Windows / Laptop)

```powershell
# 1. Tes notifikasi Telegram:
.\.venv\Scripts\python.exe hunter.py --test-telegram

# 2. Simulasi scan tanpa kirim pesan:
.\.venv\Scripts\python.exe hunter.py --dry-run

# 3. Jalankan terus-menerus di background laptop:
.\.venv\Scripts\python.exe hunter.py --loop --interval 2
```
