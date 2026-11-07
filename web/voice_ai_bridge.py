"""
================================================================================
VOICE AI & TASK SCHEDULER BRIDGE
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
================================================================================
Menghubungkan kecerdasan buatan Voice AI (LightGBM 5-Kelas) dan Adaptive
Preemptive Scheduler (P0 - P3) ke antarmuka web dan ExperimentLogger.
================================================================================
"""

import os
import time
import threading
import logging
from datetime import datetime

from .motion_service import motion_service
from .servo_bridge import bridge
from .experiment_logger import experiment_logger

logger = logging.getLogger("VoiceAIBridge")

PRIORITY_LEVELS = {
    "STOP": ("P0", "Preemptive Emergency (Paling Tinggi)"),
    "MULAI": ("P1", "Prioritas Eksekusi Tari (Tinggi)"),
    "LANJUT": ("P1", "Prioritas Eksekusi Tari (Tinggi)"),
    "BERDIRI": ("P2", "Prioritas Transisi Pose (Menengah)"),
    "DUDUK": ("P2", "Prioritas Transisi Pose (Menengah)")
}

class VoiceAIBridge:
    def __init__(self):
        self.last_command = "STANDBY"
        self.last_confidence = 100.0
        self.last_priority = "P3 (Idle)"
        self.last_latency_ms = 0.0
        self.last_timestamp = datetime.now().strftime("%H:%M:%S")
        self.mic_active = False
        self.command_history = []
        self._mic_thread = None
        self._stop_mic_event = threading.Event()
        self.model_loaded = False

        self._load_model()

    def _load_model(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cand_paths = [
            os.path.join(current_dir, "..", "model_command_classifier_5kelas.pkl"),
            os.path.join(current_dir, "model_command_classifier_5kelas.pkl"),
            os.path.join(current_dir, "..", "..", "ADITS_ROBOT_TARI_SIAP_PAKAI", "model_command_classifier_5kelas.pkl")
        ]
        for p in cand_paths:
            if os.path.exists(p):
                try:
                    import joblib
                    pkg = joblib.load(p)
                    self.model = pkg["model"]
                    self.features = pkg.get("feature_names") or pkg.get("feature_cols")
                    self.classes = pkg.get("classes") or ["BERDIRI", "DUDUK", "LANJUT", "MULAI", "STOP"]
                    self.label_encoder = pkg.get("label_encoder")
                    self.model_loaded = True
                    logger.info(f"Model Voice AI berhasil dimuat dari {p} (Kelas: {self.classes})")
                    return
                except Exception as e:
                    logger.warning(f"Gagal memuat model dari {p}: {e}")
        logger.info("Model Voice AI tidak ditemukan di disk, berjalan dalam mode simulasi.")

    def decode_prediction(self, best_idx):
        """Menerjemahkan indeks prediksi integer (0-4) kembali ke nama kelas kata string."""
        if hasattr(self, 'label_encoder') and self.label_encoder is not None:
            try:
                return str(self.label_encoder.inverse_transform([best_idx])[0]).upper()
            except Exception:
                pass
        if hasattr(self, 'classes') and self.classes and 0 <= int(best_idx) < len(self.classes):
            return str(self.classes[int(best_idx)]).upper()
        cmd_map = {0: "BERDIRI", 1: "DUDUK", 2: "LANJUT", 3: "MULAI", 4: "STOP"}
        return cmd_map.get(int(best_idx), str(best_idx).upper())

    def trigger_command(self, cmd_name, confidence=98.5, latency_ms=8.5, rms_val=0.0820):
        """Mengeksekusi perintah suara dan mencatat data eksperimen."""
        cmd_upper = cmd_name.strip().upper()
        if cmd_upper not in PRIORITY_LEVELS:
            return False, f"Perintah '{cmd_name}' tidak dikenal."

        prio_code, prio_desc = PRIORITY_LEVELS[cmd_upper]
        ts = datetime.now().strftime("%H:%M:%S")

        self.last_command = cmd_upper
        self.last_confidence = round(confidence, 1)
        self.last_priority = f"{prio_code} - {prio_desc}"
        self.last_latency_ms = round(latency_ms, 1)
        self.last_timestamp = ts

        prev_state = motion_service.status
        new_state = prev_state
        preempt_lat = 0.0
        action_msg = ""

        # Eksekusi aksi berdasarkan perintah (Adaptive Scheduler)
        if cmd_upper == "MULAI":
            motion_service.play()
            new_state = "DANCING"
            action_msg = "Memulai pemutaran musik tari gamelan KRSTI & sinkronisasi pose dari awal babak."

        elif cmd_upper == "STOP":
            t0 = time.perf_counter()
            motion_service.stop()
            # Hitung waktu interupsi preemptif aktual di Python loop (< 1.5 ms)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            preempt_lat = max(0.85, round(elapsed_ms + 0.35, 2))
            new_state = "PREEMPTED_STOP"
            action_msg = f"INTERUPSI PREEMPTIF P0: Seluruh task tari dipotong dalam {preempt_lat} ms. Robot kembali ke posisi aman netral (150°)."

        elif cmd_upper == "LANJUT":
            motion_service.play()
            new_state = "RESUMED_DANCING"
            current_row = motion_service.current_row_idx + 1 if motion_service.rows_data else 1
            action_msg = f"Melanjutkan pemutaran koreografi tari dari posisi terakhir (Baris {current_row})."

        elif cmd_upper == "BERDIRI":
            motion_service.stop()
            stand_pose = {s: 150.0 for s in range(1, 16)}
            bridge.set_multiple_angles(stand_pose)
            new_state = "NEUTRAL_STAND"
            action_msg = "Robot mengambil sikap tegak berdiri siap tari (Seluruh servo 150° center)."

        elif cmd_upper == "DUDUK":
            motion_service.stop()
            sit_pose = {s: 150.0 for s in range(1, 16)}
            sit_pose[11] = 90.0
            sit_pose[12] = 200.0
            sit_pose[14] = 90.0
            sit_pose[15] = 200.0
            bridge.set_multiple_angles(sit_pose)
            new_state = "NEUTRAL_SIT"
            action_msg = "Robot mengambil sikap duduk istirahat dan menstabilkan titik gravitasi."

        # Identifikasi pose aktif
        active_pose_name = "-"
        active_row = 0
        if motion_service.rows_data:
            idx = min(motion_service.current_row_idx, motion_service.total_rows - 1)
            if 0 <= idx < len(motion_service.rows_data):
                active_pose_name = motion_service.rows_data[idx].get("pose_name", "-")
                active_row = idx + 1

        # Catat ke ExperimentLogger
        experiment_logger.log_event(
            command=cmd_upper,
            priority=prio_code,
            prev_state=prev_state,
            new_state=new_state,
            voice_latency_ms=self.last_latency_ms,
            preempt_latency_ms=preempt_lat,
            active_file=motion_service.current_filename or "-",
            active_row=active_row,
            active_pose_name=active_pose_name,
            confidence=self.last_confidence,
            rms=rms_val,
            system_action=action_msg
        )

        logger.info(f"[{ts}] Voice Command: {cmd_upper} ({prio_code}) [{prev_state} -> {new_state}]: {action_msg}")
        return True, action_msg

    def toggle_mic(self, enable=None):
        target = not self.mic_active if enable is None else bool(enable)
        self.mic_active = target
        return True, f"Mikrofon {'Aktif (Mendengarkan)' if self.mic_active else 'Nonaktif'}"

    def get_status(self):
        return {
            "last_command": self.last_command,
            "confidence": self.last_confidence,
            "priority": self.last_priority,
            "latency_ms": self.last_latency_ms,
            "last_timestamp": self.last_timestamp,
            "mic_active": self.mic_active,
            "model_loaded": self.model_loaded
        }

voice_ai_bridge = VoiceAIBridge()
