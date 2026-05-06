[app]
title = StockScope
package.name = stockscope
package.domain = org.stockscope
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

requirements = python3,kivy==2.3.0,kivymd,yfinance,pandas,numpy,requests,urllib3,charset-normalizer,certifi,frozendict,multitasking,peewee,websockets,curl_cffi

# Android orientation
orientation = portrait

# Android
android.permissions = INTERNET
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a

# Buildozer
log_level = 2
warn_on_root = 1
