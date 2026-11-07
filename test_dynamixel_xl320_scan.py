"""
================================================================================
SKRIP DIAGNOSTIK & SCAN MOTOR SERVO DYNAMIXEL XL-320 (PROTOCOL 2.0)
ADITS KRSTI - Tim Peneliti Dewantara (Universitas Negeri Malang)
================================================================================
Dapat dijalankan langsung di Raspberry Pi 4 (/dev/ttyUSB0) maupun Windows (COMx).
Fungsi:
1. Mendeteksi port serial ROBOTIS U2D2 secara otomatis.
2. Memindai ID servo (ID 1 - 20) pada baudrate 1.000.000 bps dan 57.600 bps.
3. Menampilkan status voltase catu daya (memastikan tegangan 7.4V masuk dari PCB).
4. Menjalankan uji kedip LED warna-warni (Merah -> Hijau -> Biru) pada servo yang terdeteksi.
================================================================================
"""

import sys
import os
import time
import glob
import platform

try:
    from dynamixel_sdk import (
        PortHandler,
        PacketHandler,
        COMM_SUCCESS
    )
except ImportError:
    print("[ERROR] Pustaka 'dynamixel-sdk' belum terinstal!")
    print("Silakan jalankan: pip install dynamixel-sdk")
    sys.exit(1)

# Parameter Kontrol XL-320 (Control Table Protocol 2.0)
PROTOCOL_VERSION        = 2.0
ADDR_MODEL_NUMBER       = 0   # 2 byte (350 untuk XL-320)
ADDR_FIRMWARE_VERSION   = 2   # 1 byte
ADDR_TORQUE_ENABLE      = 24  # 1 byte (0: off, 1: on)
ADDR_LED                = 25  # 1 byte (0:off, 1:red, 2:green, 3:yellow, 4:blue, 5:purple, 6:cyan, 7:white)
ADDR_GOAL_POSITION      = 30  # 2 byte (0 - 1023)
ADDR_PRESENT_POSITION   = 37  # 2 byte (0 - 1023)
ADDR_PRESENT_VOLTAGE    = 45  # 1 byte (0.1V unit, misal 74 = 7.4V)
ADDR_PRESENT_TEMP       = 46  # 1 byte (derajat Celcius)

BAUDRATES_TO_CHECK      = [1000000, 57600, 115200]
SCAN_ID_RANGE           = range(1, 21) # Pindai ID 1 sampai 20

def detect_default_port():
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if ports:
            # Cari port yang mengandung FTDI / U2D2 / USB Serial
            for p in ports:
                if any(k in (p.description or "").lower() for k in ["ftdi", "u2d2", "usb serial", "ch340", "cp210"]):
                    return p.device
            return ports[0].device
    except Exception:
        pass

    system_os = platform.system()
    if system_os == "Linux":
        usb_ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
        if usb_ports:
            return usb_ports[0]
        return "/dev/ttyUSB0"
    elif system_os == "Windows":
        return "COM3"
    return "/dev/ttyUSB0"

def scan_dynamixel(port_name, baudrate):
    print(f"\n--- Memindai Port: {port_name} pada Baudrate: {baudrate} bps (Protocol 2.0) ---")
    portHandler = PortHandler(port_name)
    packetHandler = PacketHandler(PROTOCOL_VERSION)

    try:
        if not portHandler.openPort():
            print(f"  [GAGAL] Tidak dapat membuka port {port_name}. Periksa koneksi USB atau hak akses dialout.")
            return []
    except Exception as e:
        print(f"  [GAGAL] Tidak dapat membuka port {port_name}: {e}")
        return []

    if not portHandler.setBaudRate(baudrate):
        print(f"  [GAGAL] Gagal menyetel baudrate ke {baudrate} bps.")
        portHandler.closePort()
        return []

    found_servos = []
    for dxl_id in SCAN_ID_RANGE:
        # Ping servo
        model_number, dxl_comm_result, dxl_error = packetHandler.ping(portHandler, dxl_id)
        if dxl_comm_result == COMM_SUCCESS:
            # Baca Voltase (Address 45)
            voltage_raw, _, _ = packetHandler.read1ByteTxRx(portHandler, dxl_id, ADDR_PRESENT_VOLTAGE)
            voltage = voltage_raw / 10.0 if voltage_raw > 0 else 0.0

            # Baca Posisi Saat Ini (Address 37)
            pos_raw, _, _ = packetHandler.read2ByteTxRx(portHandler, dxl_id, ADDR_PRESENT_POSITION)
            pos_deg = (pos_raw / 1023.0) * 300.0 if pos_raw is not None else 0.0

            # Baca Suhu (Address 46)
            temp_raw, _, _ = packetHandler.read1ByteTxRx(portHandler, dxl_id, ADDR_PRESENT_TEMP)

            servo_info = {
                "id": dxl_id,
                "model": model_number,
                "voltage": voltage,
                "position_raw": pos_raw,
                "position_deg": pos_deg,
                "temperature": temp_raw,
                "portHandler": portHandler,
                "packetHandler": packetHandler
            }
            found_servos.append(servo_info)
            print(f"  -> [DITEMUKAN!] Servo ID: {dxl_id} | Model: {model_number} | Tegangan: {voltage:.1f}V | Sudut: {pos_deg:.1f}° | Suhu: {temp_raw}°C")

    portHandler.closePort()
    return found_servos

def test_blink_led(port_name, baudrate, dxl_id):
    portHandler = PortHandler(port_name)
    packetHandler = PacketHandler(PROTOCOL_VERSION)
    if not portHandler.openPort() or not portHandler.setBaudRate(baudrate):
        return

    print(f"\n[UJI VISUAL] Menguji kedip LED pada Servo ID {dxl_id}...")
    colors = [
        (1, "Merah"),
        (2, "Hijau"),
        (4, "Biru"),
        (7, "Putih"),
        (0, "Mati")
    ]
    for color_val, color_name in colors:
        packetHandler.write1ByteTxRx(portHandler, dxl_id, ADDR_LED, color_val)
        print(f"  -> LED Servo ID {dxl_id}: {color_name}")
        time.sleep(0.4)

    portHandler.closePort()

def main():
    print("=" * 75)
    print("  SCANNER & DIAGNOSTIK DYNAMIXEL XL-320 (ADITS KRSTI)")
    print("=" * 75)
    
    port_target = sys.argv[1] if len(sys.argv) > 1 else detect_default_port()
    print(f"Port Target yang akan dipindai: {port_target}")
    print("Pastikan:")
    print(" 1. Adaptor DC 12V sudah dicolokkan ke PCB Ungu dan saklar posisi ON.")
    print(" 2. Kabel TTL 3-pin terhubung dari U2D2 ke header PCB.")
    print(" 3. Kabel USB U2D2 tertancap kencang ke Raspberry Pi / PC.")

    all_found = []
    active_baud = None

    for baud in BAUDRATES_TO_CHECK:
        servos = scan_dynamixel(port_target, baud)
        if servos:
            all_found = servos
            active_baud = baud
            break

    print("\n" + "=" * 75)
    print("  HASIL PEMINDAIAN:")
    print("=" * 75)
    if not all_found:
        print("[TIDAK ADA PERANGKAT TERDETEKSI]")
        print("Solusi Pengecekan:")
        print("1. Cek suplai 12V: Apakah lampu indikator LED pada PCB ungu menyala?")
        print("2. Cek tegangan output buck converter di PCB (harus ~7.4V untuk XL-320).")
        print("3. Cek izin serial di Linux: 'sudo chmod 666 /dev/ttyUSB0' atau tambahkan user ke grup dialout.")
        print("4. Cek apakah U2D2 terdaftar di sistem ('lsusb' di Linux).")
    else:
        print(f"Berhasil menemukan {len(all_found)} servo pada baudrate {active_baud} bps!")
        for s in all_found:
            print(f"  * Servo ID {s['id']}: Tegangan {s['voltage']:.1f}V (Normal 7.4V), Posisi {s['position_deg']:.1f}°")
            if s['voltage'] < 6.0:
                print(f"    [PERINGATAN] Tegangan servo ID {s['id']} rendah ({s['voltage']:.1f}V)! Pastikan PSU 12V menyala.")
            
            # Jalankan uji LED
            test_blink_led(port_target, active_baud, s['id'])

    print("=" * 75)

if __name__ == "__main__":
    main()
