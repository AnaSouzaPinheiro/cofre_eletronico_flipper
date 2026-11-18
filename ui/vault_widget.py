"""Cofre desenhado com QPainter. Animação única: 0..1 (roda/trancas -> porta)."""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Property
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from core.vault_state import VaultState
from ui.styles import C

STATE_COLOR = {
    VaultState.LOCKED: QColor(C["red"]),
    VaultState.AWAITING: QColor(C["amber"]),
    VaultState.UNLOCKED: QColor(C["green"]),
}


def _clamp(v):
    return max(0.0, min(1.0, v))


class VaultWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(430, 430)
        self._p = 0.0
        self._phase = 0.0
        self._state = VaultState.LOCKED
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _get_p(self):
        return self._p

    def _set_p(self, v):
        self._p = v
        self.update()

    progress = Property(float, _get_p, _set_p)

    def _tick(self):
        if self._state is VaultState.AWAITING:
            self._phase += 0.035
            self.update()

    def set_state(self, state: VaultState):
        self._state = state
        target = 1.0 if state is VaultState.UNLOCKED else 0.0
        self._anim.stop()
        if abs(self._p - target) > 1e-3:
            self._anim.setDuration(int(2200 * abs(target - self._p)) + 300)
            self._anim.setStartValue(self._p)
            self._anim.setEndValue(target)
            self._anim.start()
        self.update()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h) - 16
        cx, cy = w / 2, h / 2
        col = STATE_COLOR[self._state]
        wp = _clamp(self._p / 0.35)            # roda + trancas
        dp = _clamp((self._p - 0.3) / 0.7)     # porta

        # halo de estado
        g = QRadialGradient(QPointF(cx, cy), side * 0.8)
        halo = QColor(col); halo.setAlpha(45)
        g.setColorAt(0, halo); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g)

        # moldura metálica
        body = QRectF(cx - side / 2, cy - side / 2, side, side)
        fg = QLinearGradient(body.topLeft(), body.bottomRight())
        fg.setColorAt(0, QColor("#566170")); fg.setColorAt(0.5, QColor("#1d242d")); fg.setColorAt(1, QColor("#3b4553"))
        p.setPen(QPen(QColor("#080b0f"), 2)); p.setBrush(fg)
        p.drawRoundedRect(body, 24, 24)
        m = side * 0.075
        p.setPen(Qt.NoPen); p.setBrush(QColor("#0c1015"))
        for x, y in ((body.left() + m / 2, body.top() + m / 2), (body.right() - m / 2, body.top() + m / 2),
                     (body.left() + m / 2, body.bottom() - m / 2), (body.right() - m / 2, body.bottom() - m / 2)):
            p.drawEllipse(QPointF(x, y), 4, 4)

        # interior
        inner = body.adjusted(m, m, -m, -m)
        ig = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        ig.setColorAt(0, QColor("#04070a")); ig.setColorAt(1, QColor("#0e151c"))
        p.setBrush(ig); p.drawRoundedRect(inner, 14, 14)
        p.save()
        clip = QPainterPath(); clip.addRoundedRect(inner, 14, 14); p.setClipPath(clip)
        glow = QRadialGradient(inner.center(), inner.width() * 0.7)
        gc = QColor(C["green"]); gc.setAlpha(int(120 * dp))
        glow.setColorAt(0, gc); glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(inner, glow)
        p.setOpacity(0.25 + 0.75 * dp)
        for frac in (0.5, 0.88):
            y = inner.top() + inner.height() * frac
            p.setPen(QPen(QColor("#2d3846"), 4)); p.drawLine(QPointF(inner.left(), y), QPointF(inner.right(), y))
            bx = inner.left() + inner.width() * 0.18
            for k in range(3):
                bar = QRectF(bx + k * inner.width() * 0.2, y - 24, inner.width() * 0.16, 22)
                bg = QLinearGradient(bar.topLeft(), bar.bottomLeft())
                bg.setColorAt(0, QColor("#f3d675")); bg.setColorAt(1, QColor("#9a7410"))
                p.setPen(QPen(QColor("#5a4408"), 1)); p.setBrush(bg); p.drawRoundedRect(bar, 3, 3)
        p.restore()

        # dobradiças
        p.setPen(Qt.NoPen); p.setBrush(QColor("#7b8696"))
        for fy in (0.2, 0.8):
            p.drawRoundedRect(QRectF(inner.left() - m * 0.6, inner.top() + inner.height() * fy - 14, m * 0.7, 28), 3, 3)

        # porta
        W, H = inner.width(), inner.height()
        sx = max(0.06, math.cos(dp * 1.4))
        p.save()
        p.translate(inner.left(), inner.center().y())
        p.scale(sx, 1.0)
        self._paint_door(p, W, H, wp, col)
        p.restore()

    def _paint_door(self, p, W, H, wp, col):
        door = QRectF(0, -H / 2, W, H)
        dg = QLinearGradient(0, 0, W, 0)
        dg.setColorAt(0, QColor("#6a7482")); dg.setColorAt(0.5, QColor("#2e3641")); dg.setColorAt(1, QColor("#4d5764"))
        p.setPen(QPen(QColor("#0f1317"), 2)); p.setBrush(dg)
        p.drawRoundedRect(door, 14, 14)
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
        p.drawRoundedRect(door.adjusted(12, 12, -12, -12), 10, 10)

        # trancas (recolhem junto com a roda)
        ext = 20 * (1 - wp)
        p.setPen(QPen(QColor("#0f1317"), 1)); p.setBrush(QColor("#9aa4b2"))
        for fy in (-0.3, 0.0, 0.3):
            p.drawRect(QRectF(W - 6, fy * H - 7, 6 + ext, 14))
        # rebites
        p.setPen(Qt.NoPen); p.setBrush(QColor("#1a2028"))
        for x in (24, W - 24):
            for y in (-H / 2 + 24, H / 2 - 24):
                p.drawEllipse(QPointF(x, y), 5, 5)

        # título gravado
        f = QFont("Segoe UI", 10, QFont.Bold); f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        p.setFont(f); p.setPen(QColor(255, 255, 255, 110))
        p.drawText(QRectF(0, -H * 0.43, W, 24), Qt.AlignCenter, "SECURE VAULT")

        # roda
        R = min(W, H) * 0.19
        c = QPointF(W / 2, -H * 0.03)
        if self._state is VaultState.AWAITING:
            for k in (0, 0.5):
                t = (self._phase + k) % 1.0
                a = QColor(col); a.setAlpha(int(170 * (1 - t)))
                p.setPen(QPen(a, 2)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(c, R * (1.25 + t * 0.9), R * (1.25 + t * 0.9))
        rg = QRadialGradient(c, R * 1.25)
        rg.setColorAt(0, QColor("#46505c")); rg.setColorAt(1, QColor("#161b21"))
        p.setPen(QPen(QColor("#0b0e12"), 2)); p.setBrush(rg)
        p.drawEllipse(c, R * 1.25, R * 1.25)
        p.save()
        p.translate(c); p.rotate(wp * 270)
        p.setPen(QPen(QColor("#a7b0bd"), R * 0.13, Qt.SolidLine, Qt.RoundCap))
        for i in range(6):
            a = math.radians(i * 60)
            p.drawLine(QPointF(0, 0), QPointF(math.cos(a) * R, math.sin(a) * R))
            p.setBrush(QColor("#6b7584")); p.setPen(QPen(QColor("#0b0e12"), 1))
            p.drawEllipse(QPointF(math.cos(a) * R, math.sin(a) * R), R * 0.13, R * 0.13)
            p.setPen(QPen(QColor("#a7b0bd"), R * 0.13, Qt.SolidLine, Qt.RoundCap))
        p.restore()
        hub = QRadialGradient(c, R * 0.35)
        hc = QColor(col); hc.setAlpha(230)
        hub.setColorAt(0, hc); hub.setColorAt(1, QColor("#1b2129"))
        p.setPen(QPen(QColor("#0b0e12"), 2)); p.setBrush(hub)
        p.drawEllipse(c, R * 0.35, R * 0.35)

        # placa do leitor
        plate = QRectF(W * 0.28, H * 0.31, W * 0.44, H * 0.1)
        p.setPen(QPen(QColor("#5b6674"), 1.5)); p.setBrush(QColor("#0d1218"))
        p.drawRoundedRect(plate, 6, 6)
        lc = QPointF(plate.left() + 18, plate.center().y())
        lg = QRadialGradient(lc, 14)
        gl = QColor(col); gl.setAlpha(170)
        lg.setColorAt(0, gl); lg.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen); p.setBrush(lg); p.drawEllipse(lc, 14, 14)
        p.setBrush(col); p.drawEllipse(lc, 5, 5)
        f2 = QFont("Segoe UI", 8, QFont.DemiBold); f2.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f2); p.setPen(QColor("#8fa0b5"))
        p.drawText(plate.adjusted(32, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, "SMART CARD")
