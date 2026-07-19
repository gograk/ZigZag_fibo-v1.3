[app]

# Identitas Aplikasi
title         = ZIGZAG_FIBO
package.name  = zigzagfibo
package.domain = com.gograk.zigzagfibo

source.dir    = .
source.include_exts = py,png,jpg,kv,atlas

version = 6.0

# Entry Point
entrypoint = main.py

# Dependensi Python
# Pin KEDUANYA python3 + hostpython3 ke versi sama agar tidak error versi mismatch
# kivy==2.2.1 (bukan 2.3.0) -- 2.3.0 butuh generate config.pxi terpisah yang p4a tidak panggil
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.2.1,requests,websocket-client,plyer,certifi

# Orientasi & UI
orientation = portrait
fullscreen   = 0

# Android Permission
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,VIBRATE,POST_NOTIFICATIONS

# Android SDK / NDK
android.api             = 33
android.minapi          = 21
android.ndk_api         = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license  = True

# FIX: Tunjuk langsung ke system SDK/NDK yang sudah ada di GitHub runner.
# Ini dibaca buildozer SEBELUM mencoba download -- tidak perlu env var.
android.ndk      = 27c
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724

# Arsitektur Target
android.archs = arm64-v8a

# Ikon & Presplash
# presplash.png = solid dark PNG (#0a0a14) — menggantikan splash Kivy default
# sehingga app langsung tampil layar gelap tanpa logo/Loading...
icon.filename     = %(source.dir)s/icon.png
android.presplash = %(source.dir)s/presplash.png
android.presplash_color = #0a0a14

# Backup
android.allow_backup = True

# JANGAN tambahkan android.gradle_dependencies = (kosong di sini)
# Buildozer mem-parse nilai kosong sebagai [''] (list berisi string kosong),
# p4a lalu generate: implementation ''
# Gradle 8.x menolak string kosong ini sebagai error.
# Biarkan tidak di-set supaya p4a default ke [] (list kosong benar).

[buildozer]
log_level    = 2
warn_on_root = 1
