#!/bin/sh
cd "$(dirname "$0")"
python3 build_lobby.py
printf '\nEnterキーで閉じます。'
read dummy
