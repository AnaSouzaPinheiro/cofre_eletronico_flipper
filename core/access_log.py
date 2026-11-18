"""Registro de tentativas (memória + CSV persistente)."""
import csv
from dataclasses import dataclass, astuple
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import config

OK, DENIED, INFO = "ACEITO", "REJEITADO", "INFO"


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    event: str
    result: str
    mode: str
    device: str
    detail: str


class AccessLog(QObject):
    entry_added = Signal(object)

    def __init__(self):
        super().__init__()
        self.entries = []
        self._path = Path(__file__).resolve().parent.parent / config.LOG_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, event, result, mode="-", device="-", detail=""):
        e = LogEntry(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), event, result, mode, device, detail)
        self.entries.append(e)
        try:
            new = not self._path.exists()
            with open(self._path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                if new:
                    w.writerow(["horario", "evento", "resultado", "modo", "dispositivo", "detalhe"])
                w.writerow(astuple(e))
        except OSError:
            pass  # falha de disco não pode afetar o controle de acesso
        self.entry_added.emit(e)
        return e
