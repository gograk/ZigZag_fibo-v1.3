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
# FIX: pin KEDUANYA python3 + hostpython3 ke versi yang sama
# Python 3.11.9 dipilih karena pyjnius 1.7.0 punya binary wheel Android untuk 3.11
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,requests,websocket-client,plyer,certifi

# ── Orientasi & UI ────────────────────────────────────────────────────────────
orientation = portrait
fullscreen   = 0

# ── Android Permission ────────────────────────────────────────────────────────
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,VIBRATE,POST_NOTIFICATIONS

# ── Android SDK / NDK ─────────────────────────────────────────────────────────
android.api             = 33
android.minapi          = 21
# FIX: pakai NDK 27.3 yang sudah ada di GitHub runner (tidak perlu download)
# NDK path di-set via env var ANDROIDNDK di workflow
android.ndk             = 27.3.13750724
android.ndk_api         = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license  = True

# ── Arsitektur Target ─────────────────────────────────────────────────────────
android.archs = arm64-v8a
# android.archs = arm64-v8a, armeabi-v7a

# ── Ikon ──────────────────────────────────────────────────────────────────────
icon.filename = %(source.dir)s/icon.png

# ── Backup ────────────────────────────────────────────────────────────────────
android.allow_backup = True

# ── Gradle extra ─────────────────────────────────────────────────────────────
android.gradle_dependencies =

[buildozer]
log_level    = 2
warn_on_root = 1
