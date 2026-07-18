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
# Pin KEDUANYA python3 + hostpython3 ke versi sama agar tidak error versi mismatch
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.2.1,requests,websocket-client,plyer,certifi

# ── Orientasi & UI ────────────────────────────────────────────────────────────
orientation = portrait
fullscreen   = 0

# ── Android Permission ────────────────────────────────────────────────────────
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,VIBRATE,POST_NOTIFICATIONS

# ── Android SDK / NDK ─────────────────────────────────────────────────────────
android.api             = 33
android.minapi          = 21
android.ndk_api         = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license  = True

# FIX: Tunjuk langsung ke system SDK/NDK yang sudah ada di GitHub runner.
# Ini dibaca buildozer SEBELUM mencoba download — tidak perlu env var.
# Format android.ndk harus nama release (misal 27c), BUKAN package version (27.3.x).
android.ndk     = 27c
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724

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
