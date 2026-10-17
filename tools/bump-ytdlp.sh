#!/bin/bash
# Dokumentasi: Skrip pembantu untuk meng-update versi yt-dlp
# karena proses update kini di-pin demi keamanan.
#
# Butuh uv (https://docs.astral.sh/uv/). --universal wajib agar lockfile tetap
# bisa dipasang dengan --require-hashes di semua Python yang didukung (>=3.10).
#
# uv pip compile requirements.in --universal --generate-hashes --python-version 3.10 \
#     --upgrade-package yt-dlp -o requirements.txt

echo "Jalankan perintah ini dari root repo (butuh uv):"
echo "uv pip compile requirements.in --universal --generate-hashes --python-version 3.10 --upgrade-package yt-dlp -o requirements.txt"
