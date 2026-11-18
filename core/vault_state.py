"""Máquina de estados do cofre. Só é possível liberar a partir de AGUARDANDO."""
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal

import config


class VaultState(Enum):
    LOCKED = "BLOQUEADO"
    AWAITING = "AGUARDANDO AUTENTICAÇÃO"
    UNLOCKED = "ACESSO LIBERADO"


class VaultController(QObject):
    state_changed = Signal(object)
    auto_locked = Signal()

    def __init__(self):
        super().__init__()
        self._state = VaultState.LOCKED  # sempre inicia bloqueado
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_auto_lock)

    @property
    def state(self):
        return self._state

    def _set(self, s):
        if s != self._state:
            self._state = s
            self.state_changed.emit(s)

    def begin_authentication(self) -> bool:
        if self._state is not VaultState.LOCKED:
            return False
        self._set(VaultState.AWAITING)
        return True

    def grant(self) -> bool:
        if self._state is not VaultState.AWAITING:
            return False
        self._set(VaultState.UNLOCKED)
        if config.AUTO_LOCK_SECONDS > 0:
            self._timer.start(config.AUTO_LOCK_SECONDS * 1000)
        return True

    def deny(self):
        if self._state is VaultState.AWAITING:
            self._set(VaultState.LOCKED)

    def lock(self):
        self._timer.stop()
        self._set(VaultState.LOCKED)

    def _on_auto_lock(self):
        if self._state is VaultState.UNLOCKED:
            self.lock()
            self.auto_locked.emit()
