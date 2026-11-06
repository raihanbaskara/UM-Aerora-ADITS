"""
================================================================================
EXPERIMENT LOGGER & SCIENTIFIC DATA ACQUISITION
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
================================================================================
Mencatat seluruh metrik pengujian eksperimental (timestamp, transisi state,
latensi inferensi Voice AI, waktu preemption scheduler P0-P3, pose aktif,
serta fitur ekspor CSV & clipboard untuk laporan ilmiah / skripsi).
================================================================================
"""

import io
import csv
import time
import threading
from datetime import datetime

class ExperimentLogger:
    def __init__(self):
        self.logs = []
        self.trial_counter = 0
        self.latest_event = {
            "id": 0,
            "timestamp": "-",
            "command": "STANDBY",
            "priority": "P3",
            "prev_state": "IDLE",
            "new_state": "IDLE",
            "voice_latency_ms": 0.0,
            "preempt_latency_ms": 0.0,
            "active_file": "-",
            "active_row": 0,
            "active_pose_name": "-",
            "confidence": 100.0,
            "rms": 0.0000,
            "system_action": "Sistem siap merekam data pengujian."
        }
        self._lock = threading.Lock()

    def log_event(self, command, priority, prev_state, new_state,
                  voice_latency_ms=8.5, preempt_latency_ms=0.0,
                  active_file="-", active_row=0, active_pose_name="-",
                  confidence=98.5, rms=0.0820, system_action=""):
        """Menambahkan satu baris data eksperimen baru ke log."""
        with self._lock:
            self.trial_counter += 1
            now = datetime.now()
            ts_str = now.strftime("%H:%M:%S") + f".{int(now.microsecond / 1000):03d}"

            entry = {
                "id": self.trial_counter,
                "timestamp": ts_str,
                "command": command.upper(),
                "priority": priority.upper(),
                "prev_state": prev_state.upper(),
                "new_state": new_state.upper(),
                "transition": f"{prev_state.upper()} -> {new_state.upper()}",
                "voice_latency_ms": round(float(voice_latency_ms), 2),
                "preempt_latency_ms": round(float(preempt_latency_ms), 2),
                "active_file": active_file or "-",
                "active_row": int(active_row),
                "active_pose_name": active_pose_name or "-",
                "confidence": round(float(confidence), 1),
                "rms": round(float(rms), 4),
                "system_action": system_action
            }

            self.logs.insert(0, entry) # Log terbaru paling atas
            self.latest_event = entry

            # Batasi memori log maksimal 500 riwayat
            if len(self.logs) > 500:
                self.logs.pop()

            return entry

    def get_logs(self, limit=100):
        """Mengambil data log terbaru."""
        with self._lock:
            return {
                "latest_event": self.latest_event,
                "total_records": len(self.logs),
                "logs": self.logs[:limit]
            }

    def clear(self):
        """Mereset data log."""
        with self._lock:
            self.logs = []
            self.trial_counter = 0
            self.latest_event = {
                "id": 0,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "command": "STANDBY",
                "priority": "P3",
                "prev_state": "IDLE",
                "new_state": "IDLE",
                "voice_latency_ms": 0.0,
                "preempt_latency_ms": 0.0,
                "active_file": "-",
                "active_row": 0,
                "active_pose_name": "-",
                "confidence": 100.0,
                "rms": 0.0000,
                "system_action": "Log pengujian telah direset."
            }

    def to_csv_string(self):
        """Menghasilkan representasi string CSV dari seluruh log."""
        with self._lock:
            output = io.StringIO()
            fieldnames = [
                "Trial_ID", "Timestamp", "Command", "Priority", "Previous_State",
                "New_State", "Transition", "Voice_Latency_ms", "Preemption_Latency_ms",
                "Motion_File", "Active_Row", "Active_Pose_Name", "Confidence_Pct",
                "Audio_RMS", "System_Action"
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()

            for item in reversed(self.logs): # Urutan kronologis dari trial 1
                writer.writerow({
                    "Trial_ID": item["id"],
                    "Timestamp": item["timestamp"],
                    "Command": item["command"],
                    "Priority": item["priority"],
                    "Previous_State": item["prev_state"],
                    "New_State": item["new_state"],
                    "Transition": item["transition"],
                    "Voice_Latency_ms": item["voice_latency_ms"],
                    "Preemption_Latency_ms": item["preempt_latency_ms"],
                    "Motion_File": item["active_file"],
                    "Active_Row": item["active_row"],
                    "Active_Pose_Name": item["active_pose_name"],
                    "Confidence_Pct": item["confidence"],
                    "Audio_RMS": item["rms"],
                    "System_Action": item["system_action"]
                })

            return output.getvalue()

experiment_logger = ExperimentLogger()
