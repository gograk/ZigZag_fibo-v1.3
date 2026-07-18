# ZIGZAG_FIBO v6 — Build via GitHub Actions

Dashboard trading XAUUSD berbasis ZigZag + Fibonacci, build otomatis menjadi APK Android.

## File yang Dibutuhkan di Repository

```
your-repo/
├── main.py               ← UI Kivy (responsif semua ukuran layar)
├── bot_core.py           ← Logika bot (ZigZag, Fibo, WebSocket, Telegram)
├── buildozer.spec        ← Konfigurasi build APK
├── icon.png              ← Ikon aplikasi (512×512 px)
└── .github/
    └── workflows/
        └── build-apk.yml ← GitHub Actions (otomatis build APK)
```

## Cara Pakai

### 1. Push ke GitHub
```bash
git init
git add .
git commit -m "ZIGZAG_FIBO v6"
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

### 2. GitHub Actions akan otomatis build
- Setiap push ke branch `main` → build APK langsung
- Buka tab **Actions** di GitHub repo Anda
- Tunggu hingga selesai (±15-25 menit build pertama, ±5-10 menit build berikutnya karena cache)
- Download APK dari **Artifacts** di bawah job yang selesai

### 3. Build Manual (tanpa push)
- Buka tab **Actions** → pilih workflow → klik **Run workflow**
- Pilih arch: `arm64-v8a` (default, lebih cepat) atau `arm64-v8a,armeabi-v7a` (kompatibel HP lama)

## Optimasi Kecepatan Build

| Optimasi | Dampak |
|----------|--------|
| Cache `~/.buildozer` | Build ke-2+ hemat 10-15 menit (skip download NDK/SDK) |
| Cache `~/.gradle` | Gradle tidak download ulang dependencies |
| Cache `ccache` | Kompilasi C/C++ incremental (2-3× lebih cepat) |
| Hanya `arm64-v8a` | Build 2× lebih cepat vs dual-ABI |
| SDK pre-install | Skip download lambat buildozer |

**Build pertama:** ~20-25 menit (download semua)  
**Build ke-2 dst (cache hit):** ~5-10 menit

## Fitur Aplikasi

### Tab Dashboard
- Harga XAUUSD live (WebSocket TwelveData, fallback REST)
- RSI-14 untuk 5 timeframe: 5M / 15M / 30M / 1H / 4H
- Statistik sesi: Win Rate, P&L, Max Drawdown, Uptime
- Log aktivitas bot (8 baris terakhir)
- Indikator status koneksi WebSocket

### Tab Sinyal
- Daftar sinyal hari ini dengan filter: ALL / OPEN / WIN / LOSS / PENDING
- Entry, SL, TP1 per sinyal
- P&L unrealized untuk sinyal OPEN
- Timestamp per sinyal

### Tab Fibo
- Level Fibonacci ZigZag per timeframe
- Filter per TF (5M/15M/30M/1H/4H)
- Warna: SELL merah, MID/HIGH/LOW putih, BUY hijau, SL merah gelap
- Highlight zona harga terdekat

## Responsif Semua Layar Android

Layout otomatis menyesuaikan layar via scale factor:
```python
SP = max(0.72, min(1.60, Window.width / 400.0))
```
Semua font size, padding, tinggi widget dikalikan SP — bekerja dari HP 4" hingga tablet 10".

## Icon (Tidak Load di Android?)

Icon dibuat murni dari `View + Canvas` Kivy, **tanpa font sama sekali**.  
Tidak ada `@expo/vector-icons`, tidak ada `react-native-vector-icons`, tidak ada `Ionicons`.  
Dijamin tampil di semua Android tanpa setup font tambahan.

## Telegram Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Info bot |
| `/status` | Harga live + RSI semua TF |
| `/levels` | Level Fibo semua TF |
| `/signals` | Sinyal hari ini |
| `/stats` | Statistik sesi |
| `/pnl` | PnL harian/mingguan/bulanan |
| `/help` | Daftar perintah |
