[app]
title = Mundialito
package.name = mundialchapas
package.domain = org.jose
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,webp,kv,atlas,ttf,otf,wav,ogg,mp3,flac,json,txt,csv
source.exclude_dirs = .github, bin, .buildozer, tests
version = 11.0
requirements = python3,kivy==2.3.1,pillow,sdl2_mixer,sdl2_image
orientation = portrait, landscape, portrait-reverse, landscape-reverse
fullscreen = 1
android.api = 34
android.ndk = 25b
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
