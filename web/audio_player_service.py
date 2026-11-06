"""
================================================================================
AUDIO PLAYER SERVICE (PYGAME MIXER MASTER PLAYER)
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
================================================================================
Memutar alunan musik gamelan master (audio_krsti_full_tari.wav) secara sinkron
dengan pengontrol gerakan tari, interupsi vokal, dan telemetri web.
================================================================================
"""

import os
import time
import logging
import threading

logger = logging.getLogger("AudioPlayerService")

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    logger.warning("Pustaka 'pygame' tidak tersedia. Pemutaran musik dinonaktifkan.")

class AudioPlayerService:
    def __init__(self, audio_filename: str = "audio_krsti_full_tari.wav"):
        self.audio_filename = audio_filename
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.audio_path = os.path.join(self.base_dir, audio_filename)
        
        self.is_playing = False
        self.is_paused = False
        self.start_wall = 0.0
        self.pause_pos_sec = 0.0
        self.total_duration = 220.2  # Estimasi durasi lagu (detik)
        self._lock = threading.Lock()
        
        self._init_mixer()

    def _init_mixer(self):
        """Inisialisasi pygame mixer jika belum aktif."""
        if not PYGAME_OK:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                logger.info("Pygame mixer berhasil diinisialisasi untuk AudioPlayer.")
        except Exception as e:
            logger.error(f"Gagal inisialisasi pygame mixer: {e}")

    def play(self) -> bool:
        """Memulai pemutaran musik dari detik 0.0."""
        with self._lock:
            if not PYGAME_OK:
                return False
            self._init_mixer()
            if not os.path.exists(self.audio_path):
                logger.error(f"Berkas audio tidak ditemukan di: {self.audio_path}")
                return False

            try:
                pygame.mixer.music.load(self.audio_path)
                pygame.mixer.music.play()
                self.start_wall = time.time()
                self.pause_pos_sec = 0.0
                self.is_playing = True
                self.is_paused = False
                logger.info(f"Musik gamelan KRSTI dimulai: {self.audio_filename}")
                return True
            except Exception as e:
                logger.error(f"Gagal memutar musik: {e}")
                return False

    def pause(self) -> bool:
        """Menjeda pemutaran musik dan merekam posisi detik terakhir."""
        with self._lock:
            if not self.is_playing:
                return False
            self.pause_pos_sec = self._calc_pos_sec_locked()
            if PYGAME_OK:
                try:
                    pygame.mixer.music.pause()
                except Exception as e:
                    logger.error(f"Gagal jeda musik: {e}")
            self.is_paused = True
            self.is_playing = False
            logger.info(f"Musik gamelan dijeda pada detik {self.pause_pos_sec:.1f}s.")
            return True

    def resume(self) -> bool:
        """Melanjutkan pemutaran musik dari posisi jeda."""
        with self._lock:
            if not self.is_paused:
                return False
            if PYGAME_OK:
                try:
                    pygame.mixer.music.unpause()
                except Exception as e:
                    logger.error(f"Gagal melanjutkan musik: {e}")
            self.start_wall = time.time() - self.pause_pos_sec
            self.is_playing = True
            self.is_paused = False
            logger.info(f"Musik gamelan dilanjutkan dari detik {self.pause_pos_sec:.1f}s.")
            return True

    def stop(self) -> bool:
        """Menghentikan musik dan mereset posisi ke awal."""
        with self._lock:
            if PYGAME_OK:
                try:
                    pygame.mixer.music.stop()
                except Exception as e:
                    logger.error(f"Gagal menghentikan musik: {e}")
            self.is_playing = False
            self.is_paused = False
            self.pause_pos_sec = 0.0
            logger.info("Musik gamelan dihentikan.")
            return True

    def _calc_pos_sec_locked(self) -> float:
        if not self.is_playing:
            return self.pause_pos_sec
        if PYGAME_OK:
            try:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    return pos_ms / 1000.0
            except Exception:
                pass
        return max(0.0, time.time() - self.start_wall)

    def get_position_sec(self) -> float:
        """Mengambil posisi pemutaran saat ini dalam detik."""
        with self._lock:
            return self._calc_pos_sec_locked()

    def get_status(self) -> dict:
        """Status untuk telemetri web."""
        with self._lock:
            pos = self._calc_pos_sec_locked()
            state = "PLAYING" if self.is_playing else ("PAUSED" if self.is_paused else "STOPPED")
            return {
                "filename": self.audio_filename,
                "state": state,
                "position_sec": round(pos, 1),
                "is_playing": self.is_playing,
                "is_paused": self.is_paused
            }

audio_player = AudioPlayerService()
