#!/bin/bash
# ==============================================================================
# AERORA ADITS WEB HUB - LAUNCHER UNTUK RASPBERRY PI
# Tim Peneliti Dewantara - KRSTI Universitas Negeri Malang
# ==============================================================================

cd "$(dirname "$0")"

# Aktifkan virtual environment jika ada
if [ -d "venv" ]; then
    echo "[INFO] Mengaktifkan virtual environment 'venv'..."
    source venv/bin/activate
fi

# Jalankan server dashboard web
echo "[INFO] Menjalankan AERORA ADITS Web Hub di Raspberry Pi..."
python3 run_web_dashboard.py
