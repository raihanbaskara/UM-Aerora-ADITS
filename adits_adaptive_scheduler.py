"""
================================================================================
ADITS ADAPTIVE SCHEDULER ENGINE
================================================================================
Engine scheduler riil untuk sistem ADITS (Audio-Driven IoT Task Scheduler).
Mendukung dua mode yang dibandingkan di Bab 3.3 proposal:

  1. AdaptivePreemptiveScheduler : priority queue + preemption kooperatif.
  2. StaticFIFOScheduler         : antrean biasa, tanpa prioritas, tanpa
                                    preemption (head-of-line blocking).

CATATAN PENTING SOAL PREEMPTION DI PYTHON
------------------------------------------
Python TIDAK punya cara memaksa menghentikan thread yang sedang berjalan
(tidak ada "interrupt()" sungguhan seperti di beberapa bahasa lain).
Memaksakan itu lewat trik ctypes/exception-injection itu rapuh dan bisa
merusak state internal.

Solusi yang benar -- dan yang dipakai di sini -- adalah PREEMPTION KOOPERATIF:
setiap task yang sedang "dieksekusi" memecah pekerjaannya jadi langkah-langkah
kecil (CHECK_INTERVAL_SEC), dan di tiap langkah ia mengecek apakah
`cancel_event` sudah di-set oleh scheduler. Begitu scheduler menaruh task
berprioritas lebih tinggi ke antrean, ia men-set cancel_event milik task yang
sedang berjalan; task itu akan berhenti sendiri paling lambat satu
CHECK_INTERVAL_SEC kemudian (di sini 10 ms, jauh di bawah target latensi
proposal). Ini yang membuat sistem bisa disebut "preemptive" secara jujur.

Di robot sungguhan, badan loop `_execute()` ini nanti diganti dengan
pemanggilan actuator per langkah (misal per sudut servo kecil), bukan
`time.sleep()`. Untuk saat ini (belum ada aktuator fisik), eksekusi
disimulasikan dengan durasi task yang sudah ditentukan.
================================================================================
"""

import heapq
import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# ------------------------------------------------------------------------
# Priority levels (makin kecil angka = makin prioritas, sesuai heapq)
# ------------------------------------------------------------------------
P0_EMERGENCY = 0    # STOP -> preempt apa pun yang sedang jalan, seketika
P1_TRANSITION = 1   # MULAI, LANJUT -> memotong tugas rutin P2/P3
P2_POSTURE = 2       # BERDIRI, DUDUK -> mengalah jika muncul P0/P1
P3_ROUTINE = 3       # Sinkronisasi koreografi / DSP streaming / telemetri

PRIORITY_NAMES = {
    P0_EMERGENCY: "P0_EMERGENCY",
    P1_TRANSITION: "P1_TRANSITION",
    P2_POSTURE: "P2_POSTURE",
    P3_ROUTINE: "P3_ROUTINE",
}

CHECK_INTERVAL_SEC = 0.01  # granularitas pengecekan cancel_event (10 ms)


@dataclass
class Task:
    task_id: str
    command_name: str
    priority_level: int
    duration_sec: float
    created_at: float = field(default_factory=time.monotonic)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    status: str = "PENDING"  # PENDING, RUNNING, DONE, PREEMPTED, CANCELLED
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    on_step: Optional[Callable[["Task", float], None]] = field(default=None, repr=False)

    @property
    def response_latency_sec(self) -> Optional[float]:
        """Waktu dari task dibuat sampai mulai benar-benar dieksekusi."""
        if self.started_at is None:
            return None
        return self.started_at - self.created_at

    @property
    def wall_duration_sec(self) -> Optional[float]:
        if self.started_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.started_at


def _execute(task: Task) -> None:
    """Jalankan satu task dalam langkah-langkah kecil, bisa dipotong kapan saja."""
    task.started_at = time.monotonic()
    task.status = "RUNNING"
    elapsed = 0.0
    while elapsed < task.duration_sec:
        if task.cancel_event.is_set():
            task.status = "PREEMPTED"
            task.finished_at = time.monotonic()
            return
        step = min(CHECK_INTERVAL_SEC, task.duration_sec - elapsed)
        time.sleep(step)
        elapsed += step
        if task.on_step:
            task.on_step(task, elapsed)
    task.status = "DONE"
    task.finished_at = time.monotonic()


class AdaptivePreemptiveScheduler:
    """Mode Adaptif: queue.PriorityQueue berbobot prioritas + preemption kooperatif."""

    def __init__(self):
        self._heap: List[tuple] = []
        self._seq = itertools.count()
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._current_task: Optional[Task] = None
        self._running = True
        self.log: List[Task] = []
        self._preemption_count = 0
        self._worker = threading.Thread(target=self._run, daemon=True, name="AdaptiveSchedulerWorker")
        self._worker.start()

    def submit(self, task: Task) -> None:
        with self._lock:
            heapq.heappush(self._heap, (task.priority_level, next(self._seq), task))
            if self._current_task is not None and task.priority_level < self._current_task.priority_level:
                # Tugas baru lebih prioritas daripada yang sedang berjalan -> preempt.
                self._current_task.cancel_event.set()
                self._preemption_count += 1
        self._wakeup.set()

    def _run(self) -> None:
        while self._running:
            task = None
            with self._lock:
                if self._heap:
                    _, _, task = heapq.heappop(self._heap)
                    self._current_task = task
            if task is None:
                self._wakeup.wait(timeout=0.05)
                self._wakeup.clear()
                continue
            _execute(task)
            self.log.append(task)
            with self._lock:
                self._current_task = None

    def stop(self) -> None:
        self._running = False
        self._wakeup.set()
        self._worker.join(timeout=1.0)


class StaticFIFOScheduler:
    """Mode Statis: antrean FIFO biasa, tanpa prioritas, tanpa preemption.

    Task darurat sekalipun harus menunggu task yang sedang berjalan selesai
    100% (head-of-line blocking) -- inilah pembanding untuk uji-t.
    """

    def __init__(self):
        self._queue: List[Task] = []
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._running = True
        self.log: List[Task] = []
        self._worker = threading.Thread(target=self._run, daemon=True, name="StaticSchedulerWorker")
        self._worker.start()

    def submit(self, task: Task) -> None:
        with self._lock:
            self._queue.append(task)
        self._wakeup.set()

    def _run(self) -> None:
        while self._running:
            task = None
            with self._lock:
                if self._queue:
                    task = self._queue.pop(0)
            if task is None:
                self._wakeup.wait(timeout=0.05)
                self._wakeup.clear()
                continue
            _execute(task)  # cancel_event tidak pernah di-set di mode ini -> selalu DONE
            self.log.append(task)

    def stop(self) -> None:
        self._running = False
        self._wakeup.set()
        self._worker.join(timeout=1.0)


if __name__ == "__main__":
    # Demo singkat: tugas rutin P3 sedang "jalan" lalu STOP (P0) datang di tengah.
    print("=== DEMO: Mode Adaptif (preemptive) ===")
    sch = AdaptivePreemptiveScheduler()
    routine = Task("t1", "SINKRON_KOREOGRAFI", P3_ROUTINE, duration_sec=1.0)
    sch.submit(routine)
    time.sleep(0.3)
    stop_cmd = Task("t2", "STOP", P0_EMERGENCY, duration_sec=0.05)
    sch.submit(stop_cmd)
    time.sleep(0.5)
    sch.stop()
    print(f"  Routine : status={routine.status}, berjalan {routine.wall_duration_sec*1000:.1f}ms sebelum dipotong")
    print(f"  STOP    : status={stop_cmd.status}, latensi respons={stop_cmd.response_latency_sec*1000:.1f}ms")

    print("\n=== DEMO: Mode Statis (FIFO, tanpa preemption) ===")
    sch2 = StaticFIFOScheduler()
    routine2 = Task("t3", "SINKRON_KOREOGRAFI", P3_ROUTINE, duration_sec=1.0)
    sch2.submit(routine2)
    time.sleep(0.3)
    stop_cmd2 = Task("t4", "STOP", P0_EMERGENCY, duration_sec=0.05)
    sch2.submit(stop_cmd2)
    time.sleep(1.2)
    sch2.stop()
    print(f"  Routine : status={routine2.status}, berjalan {routine2.wall_duration_sec*1000:.1f}ms (selesai penuh)")
    print(f"  STOP    : status={stop_cmd2.status}, latensi respons={stop_cmd2.response_latency_sec*1000:.1f}ms (harus menunggu)")
