"""
================================================================================
MOTION SERVICE & CSV CHOREOGRAPHY SEQUENCER
AERORA ADITS — Robot Seni Tari Indonesia (KRSTI)
================================================================================
Membaca dan memainkan berkas koreografi tari KRSTI berbasis CSV dari folder
'gerakan_baru/' atau direktori kating. Terhubung langsung dengan ServoBridge.
================================================================================
"""

import os
import csv
import time
import glob
import threading
import logging
from .servo_bridge import bridge

logger = logging.getLogger("MotionService")

class MotionService:
    def __init__(self, motion_dir=None):
        if motion_dir is None:
            # Cari folder gerakan_baru
            current_dir = os.path.dirname(os.path.abspath(__file__))
            cand1 = os.path.join(current_dir, "..", "gerakan_baru")
            cand2 = os.path.join(current_dir, "..", "..", "gerakan baru")
            cand3 = os.path.join(current_dir, "gerakan_baru")
            if os.path.exists(cand1):
                self.motion_dir = os.path.abspath(cand1)
            elif os.path.exists(cand2):
                self.motion_dir = os.path.abspath(cand2)
            else:
                self.motion_dir = os.path.abspath(cand3)
        else:
            self.motion_dir = motion_dir

        self.current_filename = None
        self.rows_data = []         # List of dicts per row: {"name": str, "delay_ms": int, "angles": {1: 150, ...}}
        self.current_row_idx = 0
        self.total_rows = 0
        self.status = "STOPPED"     # "STOPPED", "PLAYING", "PAUSED"
        self.loop_mode = False
        self.speed_multiplier = 1.0 # 1.0x normal, 0.5x slow, 2.0x fast

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set() # Not paused initially
        self._thread = None
        self._lock = threading.Lock()

        # Otomatis muat file pertama jika ada
        files = self.list_motion_files()
        if files:
            self.load_motion_file(files[0])

    def list_motion_files(self):
        """Mendaftar semua berkas CSV di direktori gerakan."""
        if not os.path.exists(self.motion_dir):
            return []
        files = glob.glob(os.path.join(self.motion_dir, "*.csv"))
        return sorted([os.path.basename(f) for f in files])

    def load_motion_file(self, filename):
        """Mem-parsing berkas CSV koreografi tari."""
        filepath = os.path.join(self.motion_dir, filename)
        if not os.path.exists(filepath):
            logger.error(f"Berkas koreografi tidak ditemukan: {filepath}")
            return False, "Berkas tidak ditemukan"

        with self._lock:
            # Hentikan dulu jika sedang play
            if self.status == "PLAYING":
                self.stop()

            self.rows_data = []
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    reader = list(csv.reader(f))
                    if not reader:
                        return False, "Berkas CSV kosong"

                    headers = [h.strip() for h in reader[0]]

                    # Petakan indeks kolom DXL#<id>
                    dxl_map = {}
                    delay_col = None
                    for col_idx, col_name in enumerate(headers):
                        c_upper = col_name.upper()
                        if "DXL#" in c_upper:
                            try:
                                sid = int(c_upper.split("DXL#")[1])
                                dxl_map[col_idx] = sid
                            except Exception:
                                pass
                        elif "T_XL320" in c_upper or "TIME" in c_upper or col_idx == 1:
                            if delay_col is None:
                                delay_col = col_idx

                    # Baca setiap baris pose
                    for r_idx, row in enumerate(reader[1:]):
                        if not row or not any(row):
                            continue
                        pose_name = row[0].strip() if len(row) > 0 else f"Pose_{r_idx+1}"

                        # Baca delay frame
                        delay_ms = 200
                        if delay_col is not None and len(row) > delay_col:
                            try:
                                delay_ms = int(float(row[delay_col].strip().replace('"', '')))
                            except Exception:
                                delay_ms = 200

                        # Baca sudut servo
                        angles = {}
                        for c_idx, s_id in dxl_map.items():
                            if len(row) > c_idx:
                                val_str = row[c_idx].strip().replace('"', '')
                                try:
                                    angles[s_id] = float(val_str)
                                except Exception:
                                    pass

                        if angles:
                            self.rows_data.append({
                                "row_index": len(self.rows_data),
                                "pose_name": pose_name,
                                "delay_ms": delay_ms if delay_ms > 20 else 200,
                                "angles": angles
                            })

                self.current_filename = filename
                self.total_rows = len(self.rows_data)
                self.current_row_idx = 0
                self.status = "STOPPED"
                logger.info(f"Berhasil memuat koreografi '{filename}': {self.total_rows} pose terdaftar.")

                # Terapkan pose pertama ke servo bridge
                if self.rows_data:
                    bridge.set_multiple_angles(self.rows_data[0]["angles"])

                return True, f"Koreografi '{filename}' ({self.total_rows} pose) berhasil dimuat."
            except Exception as e:
                logger.error(f"Gagal membaca CSV {filename}: {e}")
                return False, f"Galat membaca CSV: {e}"

    def play(self):
        """Mulai atau lanjutkan pemutaran koreografi tari."""
        if not self.rows_data:
            return False, "Tidak ada data koreografi yang dimuat"

        if self.status == "PLAYING":
            return True, "Koreografi sudah berjalan"

        if self.status == "PAUSED":
            self.status = "PLAYING"
            self._pause_event.set()
            return True, "Koreografi dilanjutkan"

        # Memulai dari STOPPED
        self.status = "PLAYING"
        self._stop_event.clear()
        self._pause_event.set()

        self._thread = threading.Thread(target=self._run_playback, daemon=True)
        self._thread.start()
        return True, "Pemutaran koreografi tari dimulai"

    def pause(self):
        """Menjeda sementara pemutaran."""
        if self.status == "PLAYING":
            self.status = "PAUSED"
            self._pause_event.clear()
            return True, "Koreografi dijeda"
        return False, "Koreografi tidak sedang berjalan"

    def stop(self):
        """Menghentikan pemutaran dan mereset ke baris awal."""
        self._stop_event.set()
        self._pause_event.set()
        self.status = "STOPPED"
        self.current_row_idx = 0

        # Kembalikan semua servo ke posisi aman berdiri tegak (150 derajat)
        neutral_angles = {s_id: 150.0 for s_id in range(1, 16)}
        bridge.set_multiple_angles(neutral_angles)
        return True, "Koreografi dihentikan. Robot kembali ke posisi netral (150°)."

    def step_next(self):
        """Maju satu langkah pose secara manual."""
        if not self.rows_data:
            return False, "Data kosong"
        if self.status == "PLAYING":
            self.pause()

        with self._lock:
            if self.current_row_idx < self.total_rows - 1:
                self.current_row_idx += 1
            else:
                self.current_row_idx = 0
            current_pose = self.rows_data[self.current_row_idx]
            bridge.set_multiple_angles(current_pose["angles"])

        return True, f"Pindah ke Pose {self.current_row_idx + 1}: {current_pose['pose_name']}"

    def step_prev(self):
        """Mundur satu langkah pose secara manual."""
        if not self.rows_data:
            return False, "Data kosong"
        if self.status == "PLAYING":
            self.pause()

        with self._lock:
            if self.current_row_idx > 0:
                self.current_row_idx -= 1
            else:
                self.current_row_idx = self.total_rows - 1
            current_pose = self.rows_data[self.current_row_idx]
            bridge.set_multiple_angles(current_pose["angles"])

        return True, f"Pindah ke Pose {self.current_row_idx + 1}: {current_pose['pose_name']}"

    def set_loop(self, is_loop):
        self.loop_mode = bool(is_loop)
        return True, f"Loop mode: {'Aktif' if self.loop_mode else 'Nonaktif'}"

    def set_speed(self, multiplier):
        self.speed_multiplier = max(0.2, min(5.0, float(multiplier)))
        return True, f"Kecepatan: {self.speed_multiplier:.1f}x"

    def _run_playback(self):
        """Thread background pemutar frame koreografi."""
        logger.info(f"Loop playback dimulai untuk {self.current_filename}")
        while not self._stop_event.is_set():
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            with self._lock:
                if self.current_row_idx >= self.total_rows:
                    if self.loop_mode:
                        self.current_row_idx = 0
                    else:
                        self.status = "STOPPED"
                        self.current_row_idx = 0
                        break

                pose = self.rows_data[self.current_row_idx]
                bridge.set_multiple_angles(pose["angles"])
                delay_sec = (pose["delay_ms"] / 1000.0) / self.speed_multiplier
                self.current_row_idx += 1

            time.sleep(delay_sec)

        self.status = "STOPPED"
        logger.info("Loop playback selesai.")

    def get_status(self):
        """Mengambil data status motion saat ini."""
        current_pose_name = "-"
        if self.rows_data and 0 <= self.current_row_idx < self.total_rows:
            current_pose_name = self.rows_data[self.current_row_idx]["pose_name"]

        return {
            "filename": self.current_filename,
            "status": self.status,
            "current_row": self.current_row_idx + 1 if self.rows_data else 0,
            "total_rows": self.total_rows,
            "current_pose_name": current_pose_name,
            "loop_mode": self.loop_mode,
            "speed": self.speed_multiplier,
            "available_files": self.list_motion_files()
        }

motion_service = MotionService()
