from PySide6.QtCore import QObject, QPropertyAnimation, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QHeaderView, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QAbstractItemView)

import config
from core import access_log as alog
from core.access_log import AccessLog
from core.authenticator import AuthReason, AuthResult, Authenticator
from core.smartcard_reader import PCSCReader, ReaderError, SimulatedReader, PYSCARD_AVAILABLE
from core.vault_state import VaultController, VaultState
from ui.styles import C
from ui.vault_widget import VaultWidget

STATE_TEXT_COLOR = {VaultState.LOCKED: C["red"], VaultState.AWAITING: C["amber"], VaultState.UNLOCKED: C["green"]}


class _AuthSignals(QObject):
    finished = Signal(object)


class _AuthTask(QRunnable):
    """Executa a comunicação APDU fora da thread da interface."""
    def __init__(self, authenticator, signals):
        super().__init__()
        self.auth, self.signals = authenticator, signals

    def run(self):
        try:
            res = self.auth.authenticate()
        except Exception as e:  # qualquer falha inesperada = acesso negado
            sim = bool(getattr(self.auth.reader, "is_simulated", False))
            res = AuthResult(False, AuthReason.COMM_ERROR, f"Erro inesperado no worker: {e}", sim)
        self.signals.finished.emit(res)


def _panel():
    f = QFrame(); f.setObjectName("panel")
    return f


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Cofre Eletrônico — Laboratório de Segurança da Informação")
        self.resize(1320, 740)
        self.vault = VaultController()
        self.log = AccessLog()
        self.reader = None
        self._pool = QThreadPool.globalInstance()
        self._signals = _AuthSignals()
        self._signals.finished.connect(self._on_auth_done)
        self._busy = False
        self._build()
        self.vault.state_changed.connect(self._on_state)
        self.vault.auto_locked.connect(lambda: self._log("Bloqueio automático", alog.INFO, detail="Tempo esgotado"))
        self.log.entry_added.connect(self._add_row)
        self._refresh_readers()
        self._on_state(VaultState.LOCKED)
        self._log("Sistema iniciado", alog.INFO, detail="Cofre bloqueado")

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QHBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(18)

        left = _panel(); lv = QVBoxLayout(left); lv.setContentsMargins(20, 18, 20, 20); lv.setSpacing(12)
        t = QLabel("COFRE ELETRÔNICO"); t.setObjectName("title")
        s = QLabel("Controle de acesso por cartão inteligente (PC/SC)"); s.setObjectName("muted")
        lv.addWidget(t); lv.addWidget(s)
        self.sim_banner = QLabel("MODO SIMULAÇÃO — não é uma autenticação real")
        self.sim_banner.setObjectName("simbanner"); self.sim_banner.setAlignment(Qt.AlignCenter); self.sim_banner.hide()
        lv.addWidget(self.sim_banner)
        self.vault_w = VaultWidget(); lv.addWidget(self.vault_w, 1)
        self.status = QLabel(); self.status.setAlignment(Qt.AlignCenter)
        lv.addWidget(self.status)
        self.result = QLabel(); self.result.setObjectName("result"); self.result.setAlignment(Qt.AlignCenter)
        self.result.setWordWrap(True); self.result.setMinimumHeight(48)
        self._fx = QGraphicsOpacityEffect(self.result); self.result.setGraphicsEffect(self._fx); self._fx.setOpacity(0)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self); self._fade.setDuration(600)
        self._hide_t = QTimer(self); self._hide_t.setSingleShot(True)
        self._hide_t.timeout.connect(lambda: self._fade_to(0))
        lv.addWidget(self.result)
        row = QHBoxLayout()
        self.btn_auth = QPushButton("Iniciar autenticação"); self.btn_auth.setObjectName("primary")
        self.btn_auth.clicked.connect(self._start_auth)
        self.btn_lock = QPushButton("Bloquear cofre"); self.btn_lock.setObjectName("danger")
        self.btn_lock.clicked.connect(self._manual_lock)
        row.addWidget(self.btn_auth, 2); row.addWidget(self.btn_lock, 1)
        lv.addLayout(row)
        root.addWidget(left, 4)

        right = QVBoxLayout(); right.setSpacing(18)
        dev = _panel(); dv = QVBoxLayout(dev); dv.setContentsMargins(18, 14, 18, 16); dv.setSpacing(8)
        lb = QLabel("Dispositivo"); lb.setObjectName("section"); dv.addWidget(lb)
        self.sim_chk = QCheckBox("Modo de simulação (sem hardware)")
        self.sim_chk.toggled.connect(self._on_sim_toggled); dv.addWidget(self.sim_chk)
        self.combo = QComboBox(); dv.addWidget(self.combo)
        self.scen = QComboBox()
        for k, v in SimulatedReader.SCENARIOS.items():
            self.scen.addItem(v, k)
        self.scen.currentIndexChanged.connect(self._on_scenario)
        dv.addWidget(self.scen)
        r2 = QHBoxLayout()
        self.btn_detect = QPushButton("Detectar leitores"); self.btn_detect.clicked.connect(self._refresh_readers)
        self.btn_conn = QPushButton("Conectar"); self.btn_conn.clicked.connect(self._toggle_connection)
        r2.addWidget(self.btn_detect); r2.addWidget(self.btn_conn)
        dv.addLayout(r2)
        self.dev_info = QLabel("Nenhum dispositivo conectado"); self.dev_info.setObjectName("muted")
        self.dev_info.setWordWrap(True); dv.addWidget(self.dev_info)
        right.addWidget(dev)

        lp = _panel(); lpv = QVBoxLayout(lp); lpv.setContentsMargins(18, 14, 18, 16)
        l2 = QLabel("Registro de tentativas"); l2.setObjectName("section"); lpv.addWidget(l2)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Horário", "Evento", "Resultado", "Modo", "Detalhes"])
        self.table.verticalHeader().hide(); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setShowGrid(False)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.table.setWordWrap(False)
        lpv.addWidget(self.table)
        right.addWidget(lp, 1)
        root.addLayout(right, 5)

    # ------------------------------------------------------------ helpers
    def _mode(self):
        # Com leitor conectado, o modo do evento é o do leitor (não o do checkbox,
        # que já pode ter mudado, ex.: desconexão causada pela troca de modo).
        if self.reader is not None:
            return "SIMULAÇÃO" if self.reader.is_simulated else "REAL"
        return "SIMULAÇÃO" if self.sim_chk.isChecked() else "REAL"

    def _dev_name(self):
        return self.reader.name if self.reader else "-"

    def _log(self, event, result, detail=""):
        self.log.add(event, result, self._mode(), self._dev_name(), detail)

    def _add_row(self, e):
        r = self.table.rowCount(); self.table.insertRow(r)
        for i, v in enumerate((e.timestamp, e.event, e.result, e.mode, e.detail)):
            it = QTableWidgetItem(v)
            if i == 2:
                it.setForeground(QColor({alog.OK: C["green"], alog.DENIED: C["red"]}.get(v, C["muted"])))
            if i == 4:
                it.setToolTip(v)
            self.table.setItem(r, i, it)
        self.table.scrollToBottom()

    def _fade_to(self, v):
        self._fade.stop(); self._fade.setStartValue(self._fx.opacity()); self._fade.setEndValue(v); self._fade.start()

    def _banner(self, text, ok):
        c = C["green"] if ok else C["red"]
        bg = "#0b2a20" if ok else "#2e0f14"
        self.result.setStyleSheet(f"background:{bg}; color:{c}; border:1px solid {c};")
        self.result.setText(text); self._fade_to(1); self._hide_t.start(5000)

    # --------------------------------------------------------- device mgmt
    def _refresh_readers(self):
        if self._busy:
            return
        self.combo.clear()
        sim = self.sim_chk.isChecked()
        self.scen.setVisible(sim)
        if sim:
            self.combo.addItem("Leitor Simulado [SIMULAÇÃO]"); return
        try:
            names = PCSCReader.list_readers()
        except ReaderError as e:
            self.dev_info.setText(str(e)); self._log("Detecção de leitores", alog.INFO, str(e)); return
        for n in names:
            self.combo.addItem(n)
        fl = PCSCReader.find_flipper(names)  # heurística pelo nome; só pré-seleciona
        if fl:
            self.combo.setCurrentText(fl)
        msg = f"{len(names)} leitor(es) PC/SC encontrado(s)." if names else \
            "Nenhum leitor PC/SC encontrado. Conecte o dispositivo e tente novamente."
        if not self.reader:
            self.dev_info.setText(msg)
        self._log("Detecção de leitores", alog.INFO, msg)

    def _on_sim_toggled(self, _):
        if self.reader:
            self._disconnect("Modo alterado")
        self.vault.lock()
        self.sim_banner.setVisible(self.sim_chk.isChecked())
        self._refresh_readers(); self._update_buttons()

    def _on_scenario(self, _):
        if isinstance(self.reader, SimulatedReader):
            self.reader.scenario = self.scen.currentData()

    def _toggle_connection(self):
        if self.reader:
            self._disconnect("Desconectado pelo operador"); return
        try:
            if self.sim_chk.isChecked():
                rd = SimulatedReader(self.scen.currentData())
            else:
                if not self.combo.currentText():
                    raise ReaderError("Nenhum leitor selecionado.")
                rd = PCSCReader(self.combo.currentText())
            rd.connect()
        except ReaderError as e:
            self.reader = None
            self._log("Conexão", alog.DENIED, str(e)); self._banner(f"✖ Falha ao conectar: {e}", False)
        else:
            self.reader = rd
            self._log("Conexão", alog.OK, f"ATR={rd.atr.hex().upper()}")
        self._update_device_info(); self._update_buttons()

    def _disconnect(self, why):
        if self.reader:
            self.reader.disconnect()
            self._log("Desconexão", alog.INFO, why)
        self.reader = None
        self.vault.lock()  # sem dispositivo, cofre bloqueado
        self._update_device_info(); self._update_buttons()

    def _update_device_info(self):
        r = self.reader
        if not r:
            self.dev_info.setText("Nenhum dispositivo conectado")
        else:
            tag = "SIMULADO" if r.is_simulated else "REAL (PC/SC)"
            self.dev_info.setText(f"Conectado: {r.name}\nTipo: {tag}\nATR: {r.atr.hex().upper() or '-'}")

    # ---------------------------------------------------------- auth flow
    def _start_auth(self):
        if self._busy or not self.vault.begin_authentication():
            return
        self._busy = True; self._update_buttons()
        # O critério segue o leitor realmente conectado: um leitor simulado
        # jamais é avaliado com o critério real (sem leitor => REAL, que nega).
        rd = self.reader
        crit = config.SIMULATION_CRITERION if (rd is not None and rd.is_simulated) else config.REAL_CRITERION
        # pequena pausa para que a animação de "aguardando" seja visível
        QTimer.singleShot(700, lambda: self._pool.start(_AuthTask(Authenticator(rd, crit), self._signals)))

    def _on_auth_done(self, res):
        self._busy = False
        tag = "[SIMULAÇÃO] " if res.simulated else ""
        if res.success and self.vault.grant():
            self._log("Autenticação", alog.OK, tag + "Critério atendido")
            self._banner(f"✔ {tag}AUTENTICAÇÃO ACEITA — acesso liberado", True)
        else:
            self.vault.deny()
            self._log("Autenticação", alog.DENIED, tag + res.reason.value + (f" | {res.detail}" if res.detail else ""))
            self._banner(f"✖ {tag}AUTENTICAÇÃO REJEITADA — {res.reason.value}", False)
        if self.reader is not None and not self.reader.is_connected:
            # Conexão perdida durante a transmissão: sincroniza UI, registro e cofre (bloqueado).
            self._disconnect("Conexão perdida (falha de comunicação)")
            self._banner("✖ Conexão com o dispositivo perdida — reconecte para tentar novamente", False)
        self._update_buttons()

    def _manual_lock(self):
        if self.vault.state is VaultState.UNLOCKED:
            self.vault.lock(); self._log("Bloqueio manual", alog.INFO, "Cofre bloqueado pelo operador")

    # -------------------------------------------------------------- state
    def _on_state(self, st):
        self.vault_w.set_state(st)
        self.status.setText(f"<span style='font-size:18px;font-weight:700;letter-spacing:3px;"
                            f"color:{STATE_TEXT_COLOR[st]}'>{st.value}</span>")
        self._update_buttons()

    def _update_buttons(self):
        st = self.vault.state
        self.btn_auth.setEnabled(st is VaultState.LOCKED and not self._busy)
        self.btn_lock.setEnabled(st is VaultState.UNLOCKED)
        self.btn_conn.setText("Desconectar" if self.reader else "Conectar")
        self.btn_conn.setEnabled(not self._busy)
        self.combo.setEnabled(self.reader is None)
        self.btn_detect.setEnabled(self.reader is None and not self._busy)
        self.sim_chk.setEnabled(not self._busy)

    # -------------------------------------------------------------- fechar
    def closeEvent(self, event):
        self.vault.lock()
        # Se houver transmissão em andamento, não bloqueia o fechamento esperando o
        # lock do leitor; o PC/SC libera a conexão ao encerrar o processo.
        if self.reader is not None and not self._busy:
            try:
                self._disconnect("Janela fechada")
            except Exception:
                pass
        super().closeEvent(event)
