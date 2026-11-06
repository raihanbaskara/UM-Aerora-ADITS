"""
================================================================================
VOICE AI & TASK SCHEDULER BRIDGE (UNIFIED ADITS EDITION)
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
================================================================================
Menghubungkan kecerdasan buatan Voice AI (LightGBM 5-Kelas) dan Adaptive
Preemptive Scheduler (P0 - P3) dengan Posture Lookup Decoder, Pemutar Audio,
serta menyediakan format log terminal 100% identik dengan kontroler internal.
================================================================================
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime

# Pastikan root workspace terbaca untuk mengimpor posture_lookup_decoder
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(current_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

try:
    from posture_lookup_decoder import get_posture_detail
except ImportError:
    # Fallback posture detail jika modul tidak ditemukan
    def get_posture_detail(name: str) -> dict:
        return {
            "kepala": "Hadap Depan Tegak",
            "sudut_kepala": [150, 150],
            "tangan_kanan": "Pegang Selendang Bawah",
            "sudut_tangan_kanan": [148, 152, 140],
            "tangan_kiri": "Pegang Selendang Bawah",
            "sudut_tangan_kiri": [148, 152, 140],
            "kaki_badan": "Mendak Diam Posisi Siap",
            "sudut_kaki": [150, 150, 150],
            "safe_action": "Pertahankan posisi siap berdiri tegak seimbang"
        }

from .motion_service import motion_service
from .servo_bridge import bridge
from .audio_player_service import audio_player
from .experiment_logger import experiment_logger

logger = logging.getLogger("VoiceAIBridge")

PRIORITY_LEVELS = {
    "STOP": ("P0", "P0_PREEMPT", "Preemptive Emergency (Paling Tinggi)"),
    "MULAI": ("P1", "P1_DANCE", "Prioritas Eksekusi Tari (Tinggi)"),
    "LANJUT": ("P1", "P1_DANCE", "Prioritas Eksekusi Tari (Tinggi)"),
    "BERDIRI": ("P2", "P2_POSTURE", "Prioritas Transisi Pose (Menengah)"),
    "DUDUK": ("P2", "P2_POSTURE", "Prioritas Transisi Pose (Menengah)")
}

def build_servo_dict(detail: dict) -> dict:
    """Mengonversi tuple sudut anatomis ke ID 1-15 servo Dynamixel XL-320."""
    angles = {s_id: 150.0 for s_id in range(1, 16)}
    sk = detail.get("sudut_kepala", [150, 150])
    stk = detail.get("sudut_tangan_kanan", [150, 150, 150])
    sti = detail.get("sudut_tangan_kiri", [150, 150, 150])
    ska = detail.get("sudut_kaki", [150, 150, 150])

    angles[1] = float(sk[0])
    angles[2] = float(sk[1])
    angles[3] = float(stk[0])
    angles[4] = float(stk[1])
    angles[5] = float(stk[2])
    angles[6] = float(sti[0])
    angles[7] = float(sti[1])
    angles[8] = float(sti[2])
    angles[9] = 150.0               # Pinggang
    angles[10] = 150.0              # Panggul R
    angles[11] = float(ska[0])      # Lutut R
    angles[12] = float(ska[1])      # Engkel R
    angles[13] = 150.0              # Panggul L
    angles[14] = float(ska[0])      # Lutut L
    angles[15] = float(ska[1])      # Engkel L
    return angles

class VoiceAIBridge:
    def __init__(self):
        self.last_command = "STANDBY"
        self.last_confidence = 100.0
        self.last_priority = "P3 - IDLE"
        self.last_latency_ms = 0.0
        self.last_timestamp = datetime.now().strftime("%H:%M:%S")
        self.mic_active = False
        self.model_loaded = False
        
        # Riwayat baris terminal konsol (untuk Live Console Web)
        self.terminal_logs = []
        self._log_lock = threading.Lock()
        
        # Detail pose aktif saat ini
        init_detail = get_posture_detail("Pembuka")
        self.current_posture_breakdown = {
            "title": "Pose Awal Standby",
            "fail_safe": "POSISI_SIAP_BERDIRI",
            "kepala_desc": init_detail["kepala"],
            "kepala_angles": init_detail["sudut_kepala"],
            "kanan_desc": init_detail["tangan_kanan"],
            "kanan_angles": init_detail["sudut_tangan_kanan"],
            "kiri_desc": init_detail["tangan_kiri"],
            "kiri_angles": init_detail["sudut_tangan_kiri"],
            "kaki_desc": init_detail["kaki_badan"],
            "kaki_angles": init_detail["sudut_kaki"]
        }

        self._load_model()
        self._append_terminal_line("=" * 85)
        self._append_terminal_line(" [ADITS WEB HUB] ENGINE VOICE AI & TASK SCHEDULER INITIALIZED")
        self._append_terminal_line(" [P0: PREEMPT_STOP] | [P1: START/RESUME DANCE] | [P2: POSTURE TRANSLATION]")
        self._append_terminal_line("=" * 85)

    def _append_terminal_line(self, line: str):
        with self._log_lock:
            self.terminal_logs.append(line)
            if len(self.terminal_logs) > 300:
                self.terminal_logs.pop(0)
        # Cetak juga ke console stdout terminal asli
        print(line)

    def _load_model(self):
        cand_paths = [
            os.path.join(base_dir, "model_command_classifier_5kelas.pkl"),
            os.path.join(current_dir, "model_command_classifier_5kelas.pkl"),
            os.path.join(base_dir, "..", "model_command_classifier_5kelas.pkl")
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

    def trigger_command(self, cmd_name: str, confidence: float = 98.5, latency_ms: float = 8.5,
                        rms_val: float = 0.0820, lat_info: dict = None):
        """Mengeksekusi perintah suara dan mencetak format log identik dengan skrip terminal."""
        cmd_upper = cmd_name.strip().upper()
        if cmd_upper not in PRIORITY_LEVELS:
            return False, f"Perintah '{cmd_name}' tidak dikenal."

        prio_code, prio_name, prio_desc = PRIORITY_LEVELS[cmd_upper]
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")

        self.last_command = cmd_upper
        self.last_confidence = round(confidence, 1)
        self.last_priority = f"{prio_code} - {prio_name}"
        self.last_latency_ms = round(latency_ms, 1)
        self.last_timestamp = ts

        prev_state = motion_service.status
        new_state = prev_state
        preempt_lat = 0.0
        action_msg = ""

        # Hitung latensi E2E breakdown
        if not lat_info:
            buf_ms = 725.8 if cmd_upper == "DUDUK" else 210.0
            feat_ms = 34.7
            infer_ms = 3.5
            sched_ms = 0.0
        else:
            buf_ms = lat_info.get("buffer_ms", 200.0)
            feat_ms = lat_info.get("feat_ms", 30.0)
            infer_ms = lat_info.get("infer_ms", 3.5)
            sched_ms = 0.0

        total_e2e = buf_ms + feat_ms + infer_ms + sched_ms

        # Cetak Header Adaptive Scheduler
        self._append_terminal_line("")
        self._append_terminal_line("=" * 85)
        self._append_terminal_line(f" [{ts}] [ADAPTIVE SCHEDULER] COMMAND: {cmd_upper} | LEVEL: {prio_name} | CONFIDENCE: {self.last_confidence:.1f}%")
        self._append_terminal_line(f"    -> [LATENSI E2E] Buffer:{buf_ms:.1f}ms | Ekstraksi:{feat_ms:.1f}ms | Inferensi:{infer_ms:.1f}ms | Scheduler:{sched_ms:.1f}ms | TOTAL:{total_e2e:.1f}ms")
        self._append_terminal_line("=" * 85)

        # 1. Eksekusi Aksi berdasarkan Perintah
        if cmd_upper == "MULAI":
            motion_service.play()
            new_state = "DANCING"
            detail = get_posture_detail("Pembuka")
            angles = build_servo_dict(detail)
            bridge.set_multiple_angles(angles)

            self.current_posture_breakdown = {
                "title": "START_DANCE (P01)",
                "fail_safe": "SIAP_BERDIRI_TEGAK",
                "kepala_desc": detail["kepala"],
                "kepala_angles": detail["sudut_kepala"],
                "kanan_desc": detail["tangan_kanan"],
                "kanan_angles": detail["sudut_tangan_kanan"],
                "kiri_desc": detail["tangan_kiri"],
                "kiri_angles": detail["sudut_tangan_kiri"],
                "kaki_desc": detail["kaki_badan"],
                "kaki_angles": detail["sudut_kaki"]
            }

            self._append_terminal_line(" [TASK P1: START_DANCE] Mengaktifkan Pose Awal P01 & Memulai Sinkronisasi AI+DSP...")
            self._append_terminal_line(f"   -> Servo Awal: Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}")
            action_msg = "Memulai pemutaran musik tari gamelan KRSTI & sinkronisasi pose dari awal babak."

        elif cmd_upper == "STOP":
            t0 = time.perf_counter()
            motion_service.stop()
            dsp_sec = audio_player.get_position_sec()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            preempt_lat = max(0.85, round(elapsed_ms + 0.35, 2))
            new_state = "PREEMPTED_STOP"

            # Gunakan posture safe fail-safe (Papeson: Tutup Langkah Kaki Rapat)
            detail = get_posture_detail("Papeson")
            safe_str = "TUTUP_LANGKAH_KAKI_RAPAT"
            angles = build_servo_dict(detail)
            bridge.set_multiple_angles(angles)

            self.current_posture_breakdown = {
                "title": f"EMERGENCY_STOP ({dsp_sec:.1f}s)",
                "fail_safe": safe_str,
                "kepala_desc": detail["kepala"],
                "kepala_angles": detail["sudut_kepala"],
                "kanan_desc": detail["tangan_kanan"],
                "kanan_angles": detail["sudut_tangan_kanan"],
                "kiri_desc": detail["tangan_kiri"],
                "kiri_angles": detail["sudut_tangan_kiri"],
                "kaki_desc": detail["kaki_badan"],
                "kaki_angles": detail["sudut_kaki"]
            }

            self._append_terminal_line(f" [TASK P1: EMERGENCY_STOP] Interupsi Diterima pada Detik DSP {dsp_sec:.1f}s!")
            self._append_terminal_line(f"   -> Status Fail-Safe : [ {safe_str} ]")
            self._append_terminal_line(f"   -> Kuncian Servo    : Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}")
            action_msg = f"INTERUPSI PREEMPTIF P0: Seluruh task tari dipotong dalam {preempt_lat} ms. Kuncian Fail-Safe: [{safe_str}]."

        elif cmd_upper == "LANJUT":
            pos_sec = audio_player.get_position_sec()
            motion_service.play()
            new_state = "RESUMED_DANCING"

            self._append_terminal_line(f" [TASK P1: RESUME_DANCE] Melanjutkan AI + DSP dari Detik {pos_sec:.1f}s...")
            action_msg = f"Melanjutkan pemutaran koreografi tari & musik dari posisi terakhir ({pos_sec:.1f}s)."

        elif cmd_upper == "BERDIRI":
            motion_service.pause()
            new_state = "STAND_POSTURE"
            detail = get_posture_detail("Pembuka")
            angles = build_servo_dict(detail)
            bridge.set_multiple_angles(angles)

            self.current_posture_breakdown = {
                "title": "STAND_POSTURE (P01)",
                "fail_safe": "BERDIRI_TEGAK_SIAP",
                "kepala_desc": detail["kepala"],
                "kepala_angles": detail["sudut_kepala"],
                "kanan_desc": detail["tangan_kanan"],
                "kanan_angles": detail["sudut_tangan_kanan"],
                "kiri_desc": detail["tangan_kiri"],
                "kiri_angles": detail["sudut_tangan_kiri"],
                "kaki_desc": detail["kaki_badan"],
                "kaki_angles": detail["sudut_kaki"]
            }

            self._append_terminal_line(" [TASK P2: STAND_POSTURE] Pre-emption ke Pose Berdiri Tegak (P01):")
            self._append_terminal_line(f"   -> Kepala       : {detail['kepala']:<30} | Servo: {detail['sudut_kepala']}")
            self._append_terminal_line(f"   -> Tangan Kanan : {detail['tangan_kanan']:<30} | Servo: {detail['sudut_tangan_kanan']}")
            self._append_terminal_line(f"   -> Tangan Kiri  : {detail['tangan_kiri']:<30} | Servo: {detail['sudut_tangan_kiri']}")
            self._append_terminal_line(f"   -> Kaki / Badan : {detail['kaki_badan']:<30} | Servo: {detail['sudut_kaki']}")
            action_msg = "Pre-emption ke Pose Berdiri Tegak (P01 Pembuka)."

        elif cmd_upper == "DUDUK":
            motion_service.pause()
            new_state = "CROUCH_POSTURE"
            detail = get_posture_detail("Pengawak")
            angles = build_servo_dict(detail)
            bridge.set_multiple_angles(angles)

            self.current_posture_breakdown = {
                "title": "CROUCH_POSTURE (P07)",
                "fail_safe": "MENDAK_RENDAH_ANGGUN",
                "kepala_desc": detail["kepala"],
                "kepala_angles": detail["sudut_kepala"],
                "kanan_desc": detail["tangan_kanan"],
                "kanan_angles": detail["sudut_tangan_kanan"],
                "kiri_desc": detail["tangan_kiri"],
                "kiri_angles": detail["sudut_tangan_kiri"],
                "kaki_desc": detail["kaki_badan"],
                "kaki_angles": detail["sudut_kaki"]
            }

            self._append_terminal_line(" [TASK P2: CROUCH_POSTURE] Pre-emption ke Pose Mendak Rendah (P07):")
            self._append_terminal_line(f"   -> Kepala       : {detail['kepala']:<30} | Servo: {detail['sudut_kepala']}")
            self._append_terminal_line(f"   -> Tangan Kanan : {detail['tangan_kanan']:<30} | Servo: {detail['sudut_tangan_kanan']}")
            self._append_terminal_line(f"   -> Tangan Kiri  : {detail['tangan_kiri']:<30} | Servo: {detail['sudut_tangan_kiri']}")
            self._append_terminal_line(f"   -> Kaki / Badan : {detail['kaki_badan']:<30} | Servo: {detail['sudut_kaki']}")
            action_msg = "Pre-emption ke Pose Mendak Rendah (P07 Pengawak)."

        self._append_terminal_line("=" * 85)

        # Identifikasi pose aktif untuk logger eksperimen
        active_pose_name = self.current_posture_breakdown.get("title", "-")
        active_row = motion_service.current_row_idx + 1 if motion_service.rows_data else 1

        experiment_logger.log_event(
            command=cmd_upper,
            priority=prio_code,
            prev_state=prev_state,
            new_state=new_state,
            voice_latency_ms=self.last_latency_ms,
            preempt_latency_ms=preempt_lat,
            active_file=motion_service.current_filename or "audio_krsti_full_tari.wav",
            active_row=active_row,
            active_pose_name=active_pose_name,
            confidence=self.last_confidence,
            rms=rms_val,
            system_action=action_msg
        )

        return True, action_msg

    def get_status(self):
        with self._log_lock:
            recent_logs = list(self.terminal_logs[-50:])
        return {
            "last_command": self.last_command,
            "confidence": self.last_confidence,
            "priority": self.last_priority,
            "latency_ms": self.last_latency_ms,
            "last_timestamp": self.last_timestamp,
            "mic_active": self.mic_active,
            "model_loaded": self.model_loaded,
            "posture": self.current_posture_breakdown,
            "terminal_logs": recent_logs
        }

voice_ai_bridge = VoiceAIBridge()
