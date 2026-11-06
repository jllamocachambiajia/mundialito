[app]
title = Copa Mundial de Chapas
package.name = mundialchapa
package.domain = org.jose
source.dir = .
source.include_exts = py,png,jpg,kv
source.exclude_dirs = .github, bin, .buildozer
version = 0.1
requirements = python3,kivy
orientation = portrait
fullscreen = 1

android.api = 34
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
