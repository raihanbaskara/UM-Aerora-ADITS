"""
================================================================================
TELEMETRY SERVICE
AERORA ADITS — Robot Seni Tari Indonesia (KRSTI)
================================================================================
Memantau sumber daya sistem Raspberry Pi 4 / PC (CPU, RAM, Suhu SoC, Uptime).
================================================================================
"""

import os
import time
import platform

try:
    import psutil
except ImportError:
    psutil = None

START_TIME = time.time()

def get_soc_temperature():
    """Membaca sensor suhu Raspberry Pi (/sys/class/thermal/thermal_zone0/temp)."""
    thermal_path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(thermal_path):
        try:
            with open(thermal_path, "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            pass
    # Fallback untuk Windows/Linux non-RPI: estimasi suhu normal
    return 42.5

def get_telemetry():
    """Mengembalikan metrik telemetri realtime."""
    cpu_usage = 0.0
    mem_usage = 0.0
    mem_total_gb = 0.0
    mem_used_mb = 0.0
    cpu_cores = 4

    if psutil:
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            mem_usage = mem.percent
            mem_total_gb = round(mem.total / (1024**3), 2)
            mem_used_mb = round(mem.used / (1024**2), 1)
            cpu_cores = psutil.cpu_count(logical=True) or 4
        except Exception:
            pass

    uptime_sec = int(time.time() - START_TIME)
    uptime_str = f"{uptime_sec // 3600:02d}:{(uptime_sec % 3600) // 60:02d}:{uptime_sec % 60:02d}"

    return {
        "os": f"{platform.system()} ({platform.machine()})",
        "cpu_usage": round(cpu_usage, 1),
        "cpu_cores": cpu_cores,
        "ram_usage": round(mem_usage, 1),
        "ram_used_mb": mem_used_mb,
        "ram_total_gb": mem_total_gb,
        "temperature": round(get_soc_temperature(), 1),
        "uptime": uptime_str
    }
