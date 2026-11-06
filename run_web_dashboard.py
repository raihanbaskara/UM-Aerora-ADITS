"""
================================================================================
AERORA ADITS -- WEB HUB LAUNCHER (1-KLIK)
Robot Seni Tari Indonesia (KRSTI) -- Tim Peneliti Dewantara
================================================================================
Jalankan skrip ini dari terminal:
    python run_web_dashboard.py
================================================================================
"""

import sys
import os
import socket
import logging

# Pastikan encoding console mendukung UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import uvicorn
except ImportError:
    print("[ERROR] Pustaka 'uvicorn' belum terinstal!")
    print("Silakan jalankan: pip install fastapi uvicorn")
    sys.exit(1)

def get_local_ip():
    """Mendeteksi IP LAN / WiFi aktif."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    port = 5000
    host = "0.0.0.0"
    local_ip = get_local_ip()

    print("=" * 75)
    print("  [ONLINE] AERORA ADITS -- WEB CONTROL HUB 2.0 (KRSTI)")
    print("  Universitas Negeri Malang (Tim Peneliti Dewantara)")
    print("=" * 75)
    print(f"  Status Server: ONLINE")
    print(f"  Akses Browser Laptop     : http://localhost:{port}")
    print(f"  Akses Browser HP / WiFi  : http://{local_ip}:{port}")
    print("=" * 75)
    print("  Tekan CTRL + C di terminal untuk menghentikan server.")
    print("=" * 75 + "\n")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    uvicorn.run("web.app:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
