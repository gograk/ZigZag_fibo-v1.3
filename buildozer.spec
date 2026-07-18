[app]

# ── Identitas Aplikasi ────────────────────────────────────────────────────────
title         = ZIGZAG_FIBO
package.name  = zigzagfibo
package.domain = com.gograk.zigzagfibo

source.dir    = .
source.include_exts = py,png,jpg,kv,atlas

version = 6.0

# ── Entry Point ───────────────────────────────────────────────────────────────
entrypoint = main.py

# ── Dependensi Python ─────────────────────────────────────────────────────────
# PENTING: jangan pin versi python3 (python3==x.x.x) → p4a gagal resolve.
# Biarkan p4a pilih versi Python yang kompatibel otomatis.
requirements = python3,kivy==2.3.0,requests,websocket-client,plyer,certifi

# ── Orientasi & UI ────────────────────────────────────────────────────────────
orientation = portrait
fullscreen   = 0

# ── Android Permission ────────────────────────────────────────────────────────
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,VIBRATE,POST_NOTIFICATIONS

# ── Android SDK / NDK ─────────────────────────────────────────────────────────
android.api             = 33
android.minapi          = 21
android.ndk             = 25b
android.ndk_api         = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license  = True

# ── Arsitektur Target ─────────────────────────────────────────────────────────
# arm64-v8a saja = build 2× lebih cepat.
# Uncomment baris berikut jika butuh dukungan HP lama (armeabi-v7a):
android.archs = arm64-v8a
# android.archs = arm64-v8a, armeabi-v7a

# ── Ikon ──────────────────────────────────────────────────────────────────────
icon.filename = %(source.dir)s/icon.png

# ── Backup ────────────────────────────────────────────────────────────────────
android.allow_backup = True

# ── Gradle extra ─────────────────────────────────────────────────────────────
android.gradle_dependencies =

[buildozer]
# log_level 2 = verbose, mudah debug kalau build gagal
log_level    = 2
warn_on_root = 1
