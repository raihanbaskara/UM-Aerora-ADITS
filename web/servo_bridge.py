"""
================================================================================
SERVO BRIDGE (DUAL-MODE: MOCK SIMULATOR & REAL DYNAMIXEL U2D2)
AERORA ADITS — Robot Seni Tari Indonesia (KRSTI)
================================================================================
Menyediakan abstraksi terpadu untuk pengontrolan motor servo Dynamixel XL-320:
- Mode 'MOCK' (Simulasi): Berjalan tanpa butuh hardware fisik / kabel.
- Mode 'REAL' (Hardware): Berkomunikasi via ROBOTIS U2D2 (Protocol 2.0, 1 Mbps).
================================================================================
"""

import os
import sys
import time
import glob
import platform
import logging

try:
    import serial.tools.list_ports
except ImportError:
    pass

try:
    from dynamixel_sdk import (
        PortHandler,
        PacketHandler,
        COMM_SUCCESS
    )
    DXL_SDK_AVAILABLE = True
except ImportError:
    DXL_SDK_AVAILABLE = False

logger = logging.getLogger("ServoBridge")

# Konfigurasi Register XL-320 (Protocol 2.0)
PROTOCOL_VERSION        = 2.0
ADDR_TORQUE_ENABLE      = 24
ADDR_LED                = 25
ADDR_GOAL_POSITION      = 30
ADDR_PRESENT_POSITION   = 37
ADDR_PRESENT_VOLTAGE    = 45
ADDR_PRESENT_TEMP       = 46

DEFAULT_BAUDRATE        = 1000000

# Pemetaan ID Servo Default Robot Humanoid (15 Sendi Utama)
SERVO_NAMES = {
    1: "Kepala Pan",
    2: "Kepala Tilt",
    3: "Bahu R-Pitch",
    4: "Bahu R-Roll",
    5: "Siku R",
    6: "Bahu L-Pitch",
    7: "Bahu L-Roll",
    8: "Siku L",
    9: "Pinggang",
    10: "Panggul R",
    11: "Lutut R",
    12: "Engkel R",
    13: "Panggul L",
    14: "Lutut L",
    15: "Engkel L"
}

class ServoBridge:
    def __init__(self):
        self.mode = "MOCK"  # Default 'MOCK' agar tidak terkendala hardware
        self.is_connected = False
        self.active_port = None
        self.active_baudrate = DEFAULT_BAUDRATE

        # DXL SDK Handlers (untuk mode REAL)
        self.portHandler = None
        self.packetHandler = None

        # State memori sudut servo (ID 1 sampai 24)
        self.servos = {}
        for s_id in range(1, 25):
            self.servos[s_id] = {
                "id": s_id,
                "name": SERVO_NAMES.get(s_id, f"Servo #{s_id}"),
                "goal_angle": 150.0,
                "present_angle": 150.0,
                "torque": 1,
                "voltage": 7.4,
                "temp": 32,
                "led": 0
            }

    @staticmethod
    def list_ports():
        """Mendeteksi seluruh port serial fisik di komputer/Raspberry Pi."""
        ports = []
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                ports.append({
                    "port": p.device,
                    "description": p.description or p.device,
                    "hwid": p.hwid or ""
                })
        except Exception:
            pass

        # Tambahan fallback port Linux jika pyserial belum list
        if platform.system() == "Linux":
            for dev in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
                if not any(item["port"] == dev for item in ports):
                    ports.append({"port": dev, "description": "USB Serial Device", "hwid": ""})

        # Selalu sertakan opsi SIMULATOR
        ports.insert(0, {"port": "SIMULATOR", "description": "Virtual Mock Controller (Simulasi)", "hwid": "MOCK"})
        return ports

    def connect(self, port_name="SIMULATOR", force_mock=False):
        """Menghubungkan ke port (Mock atau Real U2D2)."""
        if force_mock or port_name == "SIMULATOR" or not DXL_SDK_AVAILABLE:
            self.mode = "MOCK"
            self.is_connected = True
            self.active_port = port_name if port_name != "SIMULATOR" else "VIRTUAL_U2D2"
            logger.info("ServoBridge terhubung dalam MODE SIMULASI (MOCK)")
            return True, f"Terhubung dalam Mode Simulasi ({self.active_port})"

        # Mode REAL Hardware
        try:
            self.portHandler = PortHandler(port_name)
            self.packetHandler = PacketHandler(PROTOCOL_VERSION)

            if not self.portHandler.openPort():
                # Gagal buka port fisik, fallback ke MOCK
                self.mode = "MOCK"
                self.is_connected = True
                self.active_port = f"{port_name} (Simulasi Fallback)"
                return True, f"Port fisik tidak dapat dibuka. Beralih otomatis ke Mode Simulasi ({port_name})"

            if not self.portHandler.setBaudRate(self.active_baudrate):
                self.portHandler.closePort()
                self.mode = "MOCK"
                self.is_connected = True
                return True, "Gagal set baudrate 1 Mbps. Berjalan di Mode Simulasi."

            self.mode = "REAL"
            self.is_connected = True
            self.active_port = port_name
            logger.info(f"ServoBridge terhubung ke REAL HARDWARE di {port_name} @ {self.active_baudrate} bps")
            return True, f"Berhasil terhubung ke Hardware U2D2 ({port_name})"

        except Exception as e:
            # Fallback aman
            self.mode = "MOCK"
            self.is_connected = True
            self.active_port = f"{port_name} (Simulasi Fallback)"
            return True, f"Terjadi galat hardware: {e}. Mengaktifkan Mode Simulasi."

    def disconnect(self):
        """Memutus koneksi."""
        if self.mode == "REAL" and self.portHandler:
            try:
                self.portHandler.closePort()
            except Exception:
                pass
        self.is_connected = False
        self.mode = "MOCK"
        self.active_port = None
        return True, "Koneksi terputus."

    def set_servo_angle(self, servo_id, angle_deg):
        """Menggerakkan satu servo ke sudut tertentu (0 - 300 derajat)."""
        angle_deg = max(0.0, min(300.0, float(angle_deg)))
        reg_value = int((angle_deg / 300.0) * 1023)

        if servo_id in self.servos:
            self.servos[servo_id]["goal_angle"] = angle_deg
            self.servos[servo_id]["present_angle"] = angle_deg

        if self.mode == "REAL" and self.is_connected and self.packetHandler and self.portHandler:
            try:
                self.packetHandler.write2ByteTxRx(self.portHandler, servo_id, ADDR_GOAL_POSITION, reg_value)
            except Exception as e:
                logger.error(f"Gagal mengirim sudut ke Servo {servo_id}: {e}")

        return True

    def set_multiple_angles(self, angle_dict):
        """
        Mengirim sudut ke banyak servo sekaligus.
        angle_dict: {1: 150.0, 2: 145.0, ...}
        """
        for s_id, angle in angle_dict.items():
            self.set_servo_angle(s_id, angle)
        return True

    def get_all_servos_status(self):
        """Mengembalikan list status seluruh 15 servo utama."""
        result = []
        for s_id in range(1, 16):
            if s_id in self.servos:
                result.append(self.servos[s_id])
        return result

    def get_system_status(self):
        """Status keseluruhan koneksi."""
        return {
            "is_connected": self.is_connected,
            "mode": self.mode,
            "port": self.active_port or "Tidak Terhubung",
            "baudrate": self.active_baudrate,
            "total_servos": 15
        }

# Instance global singleton
bridge = ServoBridge()
