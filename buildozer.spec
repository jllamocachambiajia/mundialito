[app]
title = Copa Mundial de Chapas
package.name = mundialchapas
package.domain = org.jose
source.dir = .
source.include_exts = py
source.exclude_dirs = .github, bin, .buildozer
version = 6.0
requirements = python3
orientation = portrait, landscape, portrait-reverse, landscape-reverse
fullscreen = 1

android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
