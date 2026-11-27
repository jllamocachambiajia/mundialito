[app]
title = Mundialito
package.name = mundialitochapas
package.domain = org.jose
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,webp,kv,atlas,ttf,otf,wav,ogg,mp3,json,txt,csv
source.exclude_dirs = .github, bin, .buildozer, tests, server
version = 11.0

# Incluido pyjnius para Android y websocket-client para la conexion multijugador
requirements = python3==3.10.11,hostpython3==3.10.11,kivy,pillow,sdl2_mixer,sdl2_image,pyjnius,requests,certifi,chardet,filetype,idna,urllib3,six,sqlite3,websocket-client

# Permisos para conectar al VPS
android.permissions = INTERNET, ACCESS_NETWORK_STATE

# Permite conectar por HTTP y WS a la IP publica del VPS en Android 9+
android.manifest.application_arguments = android:usesCleartextTraffic="true"

orientation = portrait, landscape, portrait-reverse, landscape-reverse
fullscreen = 1

# API 33 para maxima compatibilidad con NDK 25b
android.api = 33
android.ndk = 25b
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
