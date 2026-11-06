#!/bin/bash
# ==============================================================================
# SKRIP OTOMATISASI INSTALASI ADITS PADA RASPBERRY PI 5 (EDGE GATEWAY)
# OS: Raspberry Pi OS 64-bit (Debian 12 Bookworm)
# ==============================================================================

set -e

echo "===================================================================="
echo "  [ADITS] SETUP DEPENDENSI & ENVIRONMENT PADA RASPBERRY PI 5"
echo "===================================================================="

# 1. Update & instal library sistem C/ALSA PortAudio
echo -e "\n[1/4] Menginstal dependensi sistem ALSA, PortAudio, dan Audio Drivers..."
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    libopenblas-dev \
    alsa-utils

# Instal libsdl2-mixer (opsional, jika tersedia di repo)
sudo apt install -y libsdl2-mixer-2.0-0 2>/dev/null || sudo apt install -y libsdl2-mixer-dev 2>/dev/null || true

# Pastikan hak akses direktori kerja dimiliki oleh user aktif (mengatasi permission denied)
ACTUAL_USER="${SUDO_USER:-$USER}"
sudo chown -R "$ACTUAL_USER":"$ACTUAL_USER" .
sudo chmod -R u+rwX .

# 2. Buat Virtual Environment Python (Sesuai Aturan PEP 668 Debian 12)
echo -e "\n[2/4] Membuat Virtual Environment Python (venv)..."
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment 'venv' berhasil dibuat."
else
    echo "Virtual environment 'venv' sudah ada."
fi

# Aktifkan virtual environment
source venv/bin/activate

# 3. Instal pustaka Python via pip
echo -e "\n[3/4] Menginstal pustaka Python untuk Edge Computing & AI..."
pip install --upgrade pip
pip install \
    numpy \
    pandas \
    scipy \
    soundfile \
    librosa \
    scikit-learn \
    lightgbm \
    joblib \
    openpyxl \
    psutil \
    pygame \
    pyaudio \
    matplotlib \
    seaborn

# 4. Tes verifikasi
echo -e "\n[4/4] Verifikasi impor modul inti..."
python3 -c "
import lightgbm as lgb
import librosa
import pyaudio
import psutil
import joblib
print(' -> LightGBM :', lgb.__version__)
print(' -> Librosa  :', librosa.__version__)
print(' -> PyAudio  : OK')
print(' -> psutil   : CPU', psutil.cpu_percent(), '%')
print('=== SEMUA MODUL BERHASIL DIMUAT DI RASPBERRY PI 5! ===')
"

echo -e "\n===================================================================="
echo "  INSTALASI SELESAI DENGAN SUKSES!"
echo "===================================================================="
echo "Untuk mengaktifkan environment dan menjalankan sistem:"
echo "  source venv/bin/activate"
echo "  python test_rpi5_hardware.py              (Cek hardware USB Mic & ALSA)"
echo "  python adits_unified_voice_dsp_internal.py (Jalankan kontroler utama)"
echo "===================================================================="
