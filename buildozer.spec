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
# Gunakan versi yang pasti ada di PyPI; hindari git/editable packages.
requirements = python3==3.11.9,kivy==2.3.0,requests,websocket-client,plyer,certifi

# ── Orientasi & UI ────────────────────────────────────────────────────────────
orientation = portrait
fullscreen   = 0

# ── Android Permission ────────────────────────────────────────────────────────
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,VIBRATE,POST_NOTIFICATIONS

# ── Android SDK / NDK (harus cocok dengan versi yang diinstall di CI) ─────────
android.api             = 33
android.minapi          = 21
android.ndk             = 25b
android.ndk_api         = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license  = True

# ── Arsitektur Target ─────────────────────────────────────────────────────────
# arm64-v8a saja = build 2× lebih cepat.
# Hapus tanda # pada baris berikut jika butuh armeabi-v7a (HP lama):
android.archs = arm64-v8a
# android.archs = arm64-v8a, armeabi-v7a

# ── Optimasi Build ────────────────────────────────────────────────────────────
# ccache mempercepat kompilasi C/C++ saat rebuild (hit cache NDK)
android.add_compile_options = -Wno-error=deprecated-declarations
# Nonaktifkan strip debug agar build debug lebih cepat
android.release_artifact = apk

# ── Ikon ──────────────────────────────────────────────────────────────────────
icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

# ── Backup ────────────────────────────────────────────────────────────────────
android.allow_backup = True

# ── Gradle extra ─────────────────────────────────────────────────────────────
# Parallel Gradle + Daemon = cepat pada build ke-2 dst (warmcache)
android.gradle_dependencies =

[buildozer]
log_level    = 2
warn_on_root = 1
