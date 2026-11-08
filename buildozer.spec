# (str) Title of your application
title = Mundialito

# (str) Package name
package.name = mundialitochapas

# (str) Package domain (needed for android packaging)
package.domain = org.jose

# (list) Source files to include (let it as is)
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,webp,kv,atlas,ttf,otf,wav,ogg,mp3,atlas,json,txt,csv

# (list) Application requirements
# Asegúrate de incluir python3, kivy y las librerías que uses
requirements = python3,kivy==2.3.1,pillow,sdl2_mixer,sdl2_image

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b
