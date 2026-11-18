"""
Gera capturas de tela da interface para o relatório (modo REAL, Flipper conectado).

Abre a janela sem exibi-la, executa Detectar -> Conectar -> Autenticar e salva:
  tools/evidencias/tela_1_bloqueado.png   (estado inicial)
  tools/evidencias/tela_2_liberado.png    (após autenticação com o Flipper)
  tools/evidencias/tela_3_rebloqueado.png (após bloqueio manual)

Uso:  .venv/bin/python tools/capturar_telas.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.styles import QSS  # noqa: E402

OUT = os.path.join(ROOT, "tools", "evidencias")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()

    def snap(name):
        path = os.path.join(OUT, name)
        win.grab().save(path)
        print("salvo:", path)

    steps = [
        (500, lambda: (win.sim_chk.setChecked(False), win._refresh_readers())),
        (800, lambda: snap("tela_1_bloqueado.png")),
        (300, win._toggle_connection),
        (300, win._start_auth),
        (2500, lambda: snap("tela_2_liberado.png")),
        (200, win._manual_lock),
        (1200, lambda: snap("tela_3_rebloqueado.png")),
        (100, lambda: (win.close(), app.quit())),
    ]
    t = 0
    for delay, fn in steps:
        t += delay
        QTimer.singleShot(t, fn)
    app.exec()


if __name__ == "__main__":
    main()
