"""state_machine.py — Estados operativos de Jarvis (inspirado en el video).

Estados (como en el video que recreamos):
  IDLE         — sin tareas, esperando. Avatar relajada.
  WORKING      — procesando una tarea. Avatar enfocada.
  SLEEPING     — pausa por bajo consumo. Avatar dormida.
  OVERLOADED   — saturación de carga. Avatar agitada.
  ERROR        — algo falló. Avatar preocupada.

Las transiciones son determinadas por:
  - queue_size (tareas pendientes)
  - cpu_load (psutil)
  - tasks_per_minute (rate)
  - errors_last_minute
  - inactive_seconds (sin tareas)

Cada cambio de estado se loguea para que el avatar lo refleje.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class JarvisState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    SLEEPING = "sleeping"
    OVERLOADED = "overloaded"
    ERROR = "error"


@dataclass
class SystemMetrics:
    queue_size: int = 0
    tasks_in_progress: int = 0
    tasks_completed_last_min: int = 0
    errors_last_min: int = 0
    inactive_seconds: float = 0.0
    cpu_pct: float = 0.0
    ram_pct: float = 0.0


@dataclass
class StateMachine:
    state: JarvisState = JarvisState.IDLE
    last_state_change: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    history: list = field(default_factory=list)

    def update(self, m: SystemMetrics) -> JarvisState:
        old = self.state
        new = self._decide(m)
        if new != old:
            self.history.append({
                "from": old.value, "to": new.value,
                "ts": time.time(), "metrics": m.__dict__.copy(),
            })
            self.last_state_change = time.time()
        self.state = new
        if m.tasks_in_progress > 0 or m.queue_size > 0:
            self.last_activity = time.time()
        return new

    def _decide(self, m: SystemMetrics) -> JarvisState:
        # Errores recientes dominan
        if m.errors_last_min >= 3:
            return JarvisState.ERROR

        # Saturación
        if m.cpu_pct > 85 or m.ram_pct > 90 or m.queue_size > 30:
            return JarvisState.OVERLOADED

        # Trabajando activo
        if m.tasks_in_progress > 0:
            return JarvisState.WORKING

        # Inactividad larga → sleeping
        idle_since = time.time() - self.last_activity
        if idle_since > 300:  # 5 min sin tareas
            return JarvisState.SLEEPING

        return JarvisState.IDLE

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_change_ago_s": time.time() - self.last_state_change,
            "history_count": len(self.history),
        }


def collect_metrics(queue_size: int, in_progress: int,
                    completed_recent: int = 0,
                    errors_recent: int = 0) -> SystemMetrics:
    cpu = ram = 0.0
    if HAS_PSUTIL:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
        except Exception:
            pass
    return SystemMetrics(
        queue_size=queue_size,
        tasks_in_progress=in_progress,
        tasks_completed_last_min=completed_recent,
        errors_last_min=errors_recent,
        cpu_pct=cpu,
        ram_pct=ram,
    )


# Mapeo de estado a expresión visual del avatar
AVATAR_EXPRESSION = {
    JarvisState.IDLE: {"emoji": "😌", "color": "#6BCB77", "label": "Esperando"},
    JarvisState.WORKING: {"emoji": "🤖", "color": "#4D96FF", "label": "Trabajando"},
    JarvisState.SLEEPING: {"emoji": "😴", "color": "#9B89B3", "label": "Descansando"},
    JarvisState.OVERLOADED: {"emoji": "🥵", "color": "#FF6B6B", "label": "Sobrecargada"},
    JarvisState.ERROR: {"emoji": "⚠️", "color": "#FFD93D", "label": "Error"},
}
