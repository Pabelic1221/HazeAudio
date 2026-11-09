"""
HazeAudio - drag-and-drop audio player with a glassmorphism UI.

Install:  pip install -r requirements.txt
Run:      python haze_audio.py

Shortcuts: Space play/pause | Left/Right seek 5s | Up/Down volume | Delete remove track | Ctrl+F search
"""
import array
import json
import math
import os
import random
import subprocess
import sys
import traceback
from collections import deque
from pathlib import Path
from string import Template

from PySide6.QtCore import (QAbstractNativeEventFilter, QEasingCurve, QPoint, QPointF,
                            QPropertyAnimation, QRectF, Qt, QTimer, QUrl, QVariantAnimation, Signal)
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QDesktopServices, QFont,
                           QFontMetrics, QGuiApplication, QIcon, QImage, QKeySequence,
                           QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
                           QPolygonF, QRadialGradient, QShortcut)
from PySide6.QtMultimedia import (QAudioFormat, QAudioOutput, QMediaDevices, QMediaMetaData,
                                  QMediaPlayer)
try:
    from PySide6.QtMultimedia import QAudioBufferOutput
except ImportError:  # older Qt: the app still works, just without the visualizer
    QAudioBufferOutput = None
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QSizeGrip, QSlider, QStyle, QSystemTrayIcon, QVBoxLayout, QWidget)

VERSION = "1.1.0"
APP_NAME = "HazeAudio"
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".opus", ".wma", ".weba"}
PLAYLIST_EXT = {".m3u", ".m3u8"}
COVER = 250
DATA_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "HazeAudio"
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "error.log"
SERVER_NAME = "HazeAudio-single-instance"
CREDIT_URL = "https://github.com/Pabelic1221"

# ---------------------------------------------------------------- themes
THEMES = {
    "Haze": dict(light=False, bg=("#1a1048", "#2b1a70", "#0d3a5e"),
                 blobs=("#ff4fa3", "#38bdf8", "#a78bfa", "#22d3ee"), acc=("#ff6fb5", "#8f7bff")),
    "Ocean": dict(light=False, bg=("#06203a", "#0b3b66", "#064e55"),
                  blobs=("#38bdf8", "#22d3ee", "#6366f1", "#2dd4bf"), acc=("#38bdf8", "#6ee7d9")),
    "Sunset": dict(light=False, bg=("#2a0f3a", "#5b1a4a", "#7a2e1f"),
                   blobs=("#ff7a45", "#ff4f8b", "#ffb347", "#c026d3"), acc=("#ff8a5c", "#ff4f8b")),
    "Forest": dict(light=False, bg=("#07251d", "#0f3d2e", "#16384a"),
                   blobs=("#34d399", "#a3e635", "#22d3ee", "#10b981"), acc=("#4ade80", "#2dd4bf")),
    "Rose": dict(light=False, bg=("#2b0f2a", "#4a1740", "#3a1a5c"),
                 blobs=("#fb7185", "#f0abfc", "#fda4af", "#c084fc"), acc=("#fb7185", "#e879f9")),
    "Graphite": dict(light=False, bg=("#101114", "#1c1e24", "#14171c"),
                     blobs=("#64748b", "#94a3b8", "#475569", "#7c8aa5"), acc=("#cbd5e1", "#94a3b8")),
    "Frost": dict(light=True, bg=("#e6ecfb", "#f3e8f6", "#dff3f2"),
                  blobs=("#f9a8d4", "#93c5fd", "#c4b5fd", "#99f6e4"), acc=("#a855f7", "#6366f1")),
}
BLOB_POS = ((0.12, 0.18, 0.42), (0.88, 0.22, 0.38), (0.62, 0.95, 0.46), (0.08, 0.92, 0.30))

STYLE = Template("""
QLabel { color: $txt; background: transparent; }
QLabel#muted { color: $muted; }
QPushButton { color: $txt; background: $btn; border: 1px solid $border; border-radius: 22px; font-size: 15px; }
QPushButton:hover { background: $btn_hover; }
QPushButton:pressed { background: $btn_press; }
QPushButton:checked { background: $chk; border-color: $chk_border; }
QPushButton#pill { border-radius: 16px; padding: 0 14px; font-size: 12px; }
QSlider::groove:horizontal { height: 6px; background: $groove; border-radius: 3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $a, stop:1 $b); border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: white; border: 1px solid $handle_border; }
QLineEdit { color: $txt; background: $input; border: 1px solid $border; border-radius: 15px; padding: 6px 14px; selection-background-color: $a; }
QLineEdit:focus { border-color: $chk_border; }
QListWidget { background: transparent; border: none; outline: none; color: $txt; font-size: 13px; }
QListWidget::item { padding: 10px 12px; border-radius: 12px; margin: 2px 0; }
QListWidget::item:hover { background: $item_hover; }
QListWidget::item:selected { background: $sel; color: $txt; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 4px 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu { background: $menu; color: $txt; border: 1px solid $border; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 24px 8px 14px; border-radius: 8px; }
QMenu::item:selected { background: $sel; }
QMenu::item:disabled { color: $muted; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }
""")


def build_style(t):
    if t["light"]:
        tok = dict(txt="#1f1b3d", muted="rgba(31,27,61,0.62)", btn="rgba(255,255,255,0.55)",
                   btn_hover="rgba(255,255,255,0.85)", btn_press="rgba(255,255,255,0.4)",
                   border="rgba(31,27,61,0.18)", chk="rgba(255,255,255,0.97)",
                   chk_border="rgba(120,90,200,0.7)", groove="rgba(31,27,61,0.15)",
                   handle_border="rgba(31,27,61,0.25)", input="rgba(255,255,255,0.6)",
                   item_hover="rgba(255,255,255,0.45)", sel="rgba(255,255,255,0.8)",
                   scroll="rgba(31,27,61,0.3)", menu="rgba(250,248,255,0.97)")
    else:
        tok = dict(txt="#ffffff", muted="rgba(255,255,255,0.62)", btn="rgba(255,255,255,0.12)",
                   btn_hover="rgba(255,255,255,0.24)", btn_press="rgba(255,255,255,0.08)",
                   border="rgba(255,255,255,0.25)", chk="rgba(255,255,255,0.38)",
                   chk_border="rgba(255,255,255,0.7)", groove="rgba(255,255,255,0.18)",
                   handle_border="rgba(255,255,255,0.0)", input="rgba(255,255,255,0.12)",
                   item_hover="rgba(255,255,255,0.10)", sel="rgba(255,255,255,0.22)",
                   scroll="rgba(255,255,255,0.3)", menu="rgba(26,20,64,0.96)")
    tok["a"], tok["b"] = t["acc"]
    return STYLE.safe_substitute(tok)


# ---------------------------------------------------------------- small helpers
def resource_path(name: str) -> str:
    """Find bundled files both in development and inside the PyInstaller build."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base) / name)


def install_crash_log():
    """A windowed .exe has no console, so write unexpected errors to a log file."""
    def hook(kind, value, tb):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write("".join(traceback.format_exception(kind, value, tb)) + "\n")
        except OSError:
            pass
        try:
            sys.__excepthook__(kind, value, tb)
        except Exception:
            pass
    sys.excepthook = hook


def send_to_running(paths: list) -> bool:
    """If HazeAudio is already open, hand the files to it instead of opening a second window."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(json.dumps(paths).encode("utf-8"))
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def fmt(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def read_m3u(path: str) -> list:
    try:
        text = Path(path).read_text("utf-8", errors="replace")
    except OSError:
        return []
    base = Path(path).parent
    out = []
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        p = Path(line)
        out.append(str(p if p.is_absolute() else base / p))
    return out


def lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def hue_shift(c: QColor, deg: int) -> QColor:
    return QColor.fromHsv((c.hue() + deg) % 360, c.saturation(), c.value())


def dominant_colors(img: QImage):
    """Four vivid colors taken from cover art, or None for grayscale covers."""
    small = img.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.convertToFormat(QImage.Format.Format_RGB32)
    buckets = {}
    for y in range(24):
        for x in range(24):
            h, s, v, _ = QColor(small.pixel(x, y)).getHsv()
            if h < 0 or s < 45 or v < 60:
                continue
            w = s * v / 255.0
            b = buckets.setdefault(h // 30, [0.0, 0.0, 0.0, 0.0])
            b[0] += w
            b[1] += h * w
            b[2] += s * w
            b[3] += v * w
    if not buckets:
        return None
    ranked = sorted(buckets.values(), key=lambda b: -b[0])

    def vivid(b):
        return QColor.fromHsv(int(b[1] / b[0]) % 360, int(max(b[2] / b[0], 160)), int(max(b[3] / b[0], 190)))
    c1 = vivid(ranked[0])
    c2 = vivid(ranked[1]) if len(ranked) > 1 else hue_shift(c1, 40)
    return [c1, c2, hue_shift(c1, -30), hue_shift(c2, 30)]


def make_cover(img, a: str, b: str) -> QPixmap:
    """Rounded cover art, or a themed gradient placeholder when the file has no artwork."""
    pm = QPixmap(COVER, COVER)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, COVER, COVER), 28, 28)
    p.setClipPath(clip)
    if img is not None and not img.isNull():
        scaled = QPixmap.fromImage(img).scaled(COVER, COVER, Qt.KeepAspectRatioByExpanding,
                                               Qt.SmoothTransformation)
        p.drawPixmap((COVER - scaled.width()) // 2, (COVER - scaled.height()) // 2, scaled)
    else:
        g = QLinearGradient(0, 0, COVER, COVER)
        ca, cb = QColor(a), QColor(b)
        ca.setAlpha(210)
        cb.setAlpha(210)
        g.setColorAt(0, ca)
        g.setColorAt(1, cb)
        p.fillRect(0, 0, COVER, COVER, g)
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(QFont("Segoe UI", 80))
        p.drawText(QRectF(0, 0, COVER, COVER), Qt.AlignCenter, "♪")
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 90), 1.5))
    p.drawPath(clip)
    p.end()
    return pm


def _draw_icon(p, kind, ink, checked=False):
    """Vector icons on a 24x24 grid, so they look identical on every PC (no font or emoji dependence)."""
    def stroke(width=1.9):
        p.setPen(QPen(ink, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)

    def solid(width=0.0):
        p.setPen(QPen(ink, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin) if width else Qt.NoPen)
        p.setBrush(ink)

    def poly(pts):
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

    def line(x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if kind == "play":
        solid(2.4)
        poly([(8.9, 6.6), (17.6, 12), (8.9, 17.4)])
    elif kind == "pause":
        solid()
        p.drawRoundedRect(QRectF(6.9, 5.8, 3.9, 12.4), 1.7, 1.7)
        p.drawRoundedRect(QRectF(13.2, 5.8, 3.9, 12.4), 1.7, 1.7)
    elif kind in ("prev", "next"):
        solid()
        if kind == "prev":
            p.drawRoundedRect(QRectF(5.6, 6.2, 2.5, 11.6), 1.2, 1.2)
            solid(2.0)
            poly([(18, 7.4), (10, 12), (18, 16.6)])
        else:
            p.drawRoundedRect(QRectF(15.9, 6.2, 2.5, 11.6), 1.2, 1.2)
            solid(2.0)
            poly([(6, 7.4), (14, 12), (6, 16.6)])
    elif kind == "shuffle":
        stroke()
        a = QPainterPath()
        a.moveTo(3.5, 7)
        a.lineTo(7, 7)
        a.cubicTo(12, 7, 11, 17, 16, 17)
        a.lineTo(17.5, 17)
        b = QPainterPath()
        b.moveTo(3.5, 17)
        b.lineTo(7, 17)
        b.cubicTo(12, 17, 11, 7, 16, 7)
        b.lineTo(17.5, 7)
        p.drawPath(a)
        p.drawPath(b)
        solid(0.8)
        poly([(17.2, 4.6), (21.2, 7), (17.2, 9.4)])
        poly([(17.2, 14.6), (21.2, 17), (17.2, 19.4)])
    elif kind in ("repeat", "repeat1"):
        stroke()
        a = QPainterPath()
        a.moveTo(5, 11.4)
        a.lineTo(5, 10.5)
        a.quadTo(5, 7.5, 8, 7.5)
        a.lineTo(16.5, 7.5)
        b = QPainterPath()
        b.moveTo(19, 12.6)
        b.lineTo(19, 13.5)
        b.quadTo(19, 16.5, 16, 16.5)
        b.lineTo(7.5, 16.5)
        p.drawPath(a)
        p.drawPath(b)
        solid(0.8)
        poly([(15.8, 4.9), (20.2, 7.5), (15.8, 10.1)])
        poly([(8.2, 13.9), (3.8, 16.5), (8.2, 19.1)])
        if kind == "repeat1":
            stroke(1.5)
            p.drawPolyline(QPolygonF([QPointF(10.8, 10.9), QPointF(12.3, 10.1), QPointF(12.3, 13.9)]))
    elif kind == "min":
        stroke(2.2)
        line(6.5, 12, 17.5, 12)
    elif kind == "close":
        stroke(2.1)
        line(7.2, 7.2, 16.8, 16.8)
        line(16.8, 7.2, 7.2, 16.8)
    elif kind == "gear":  # settings: three sliders (reads more clearly than a cog at small sizes)
        stroke(1.9)
        for y, kx in ((6.5, 15.5), (12, 8.5), (17.5, 14)):
            line(3.8, y, kx - 3.3, y)
            line(kx + 3.3, y, 20.2, y)
            p.drawEllipse(QPointF(kx, y), 2.4, 2.4)
    elif kind == "pin":
        stroke(1.8)
        p.setBrush(ink if checked else Qt.NoBrush)
        poly([(9, 4), (15, 4), (14.2, 10.3), (17.2, 13), (6.8, 13), (9.8, 10.3)])
        line(12, 13, 12, 20)
    elif kind == "mini":
        stroke(1.9)
        p.drawRoundedRect(QRectF(3.5, 5.5, 17, 13), 2.6, 2.6)
        solid()
        p.drawRoundedRect(QRectF(12, 11, 6, 5), 1.2, 1.2)
    elif kind == "expand":
        stroke(1.9)
        a = QPainterPath()
        a.moveTo(14, 4.8)
        a.lineTo(19.2, 4.8)
        a.lineTo(19.2, 10)
        b = QPainterPath()
        b.moveTo(10, 19.2)
        b.lineTo(4.8, 19.2)
        b.lineTo(4.8, 14)
        p.drawPath(a)
        p.drawPath(b)
        line(19, 5, 13.5, 10.5)
        line(5, 19, 10.5, 13.5)


class IconButton(QAbstractButton):
    """Round glass button with a painted vector icon. Replaces text/emoji glyphs."""
    DOT_KINDS = ("shuffle", "repeat", "repeat1")

    def __init__(self, kind, size=44, primary=False, checkable=False, danger=False, tip=""):
        super().__init__()
        self.kind, self.primary, self.danger = kind, primary, danger
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(checkable)
        self.setToolTip(tip)
        self.setAccessibleName(tip or kind)
        self.setFocusPolicy(Qt.NoFocus)

    def setKind(self, kind):
        self.kind = kind
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        th = getattr(self.window(), "theme", None) or THEMES["Haze"]
        light = th["light"]
        acc_a, acc_b = QColor(th["acc"][0]), QColor(th["acc"][1])
        base = QColor("#1f1b3d") if light else QColor("#ffffff")
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = float(self.width())
        c = QPointF(w / 2, w / 2)
        down, hov, on = self.isDown(), self._hover, self.isChecked()
        if self.primary:
            r = w / 2 - (6.5 if down else 4.5 if hov else 5.5)
            halo = QRadialGradient(c, w / 2)
            h0, h1 = QColor(acc_a), QColor(acc_a)
            h0.setAlpha(125 if hov else 90)
            h1.setAlpha(0)
            halo.setColorAt(0.68, h0)
            halo.setColorAt(1.0, h1)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(c, w / 2, w / 2)
            g = QLinearGradient(c.x() - r, c.y() - r, c.x() + r, c.y() + r)
            g.setColorAt(0, acc_a.lighter(106) if hov else acc_a)
            g.setColorAt(1, acc_b.lighter(106) if hov else acc_b)
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(255, 255, 255, 140), 1.2))
            p.drawEllipse(c, r, r)
            clip = QPainterPath()
            clip.addEllipse(c, r - 1, r - 1)
            p.setClipPath(clip)
            gloss = QLinearGradient(0, c.y() - r, 0, c.y())
            gloss.setColorAt(0, QColor(255, 255, 255, 90))
            gloss.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(c.x() - r, c.y() - r, 2 * r, r), gloss)
            p.setClipping(False)
            ink, frac = QColor("#ffffff"), 0.50
        else:
            r = w / 2 - 1
            if self.danger and hov:
                fill, ink, edge = QColor(255, 80, 90, 235), QColor("#ffffff"), QColor(255, 255, 255, 60)
            elif self.isCheckable():
                ink = acc_a if on else QColor(base.red(), base.green(), base.blue(), 175)
                fill = QColor(acc_a.red(), acc_a.green(), acc_a.blue(), 55 if on else 0)
                if hov and not on:
                    fill = QColor(255, 255, 255, 120 if light else 38)
                edge = QColor(0, 0, 0, 0)
            else:
                ink = base
                if light:
                    fill = QColor(255, 255, 255, 235 if down else 215 if hov else 150)
                    edge = QColor(31, 27, 61, 40)
                else:
                    fill = QColor(255, 255, 255, 64 if down else 52 if hov else 30)
                    edge = QColor(255, 255, 255, 60)
            p.setPen(QPen(edge, 1.0))
            p.setBrush(fill)
            p.drawEllipse(c, r, r)
            frac = 0.5 if w >= 40 else 0.6
        p.save()
        p.translate(c)
        p.scale(w * frac / 24, w * frac / 24)
        p.translate(-12, -12)
        _draw_icon(p, self.kind, ink, on)
        p.restore()
        if on and self.kind in self.DOT_KINDS:  # little "active" dot under toggles
            p.setPen(Qt.NoPen)
            p.setBrush(acc_a)
            p.drawEllipse(QPointF(c.x(), w - 4.5), 1.8, 1.8)


def paint_backdrop(p, w, h, radius, theme, blobs, border: QColor, border_w=1.5):
    path = QPainterPath()
    path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)
    p.setClipPath(path)
    c0, c1, c2 = (QColor(x) for x in theme["bg"])
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, c0)
    bg.setColorAt(0.55, c1)
    bg.setColorAt(1, c2)
    p.fillRect(QRectF(0, 0, w, h), bg)
    m = max(w, h)
    alpha = 125 if theme["light"] else 150
    for (fx, fy, fr), col in zip(BLOB_POS, blobs):
        g = QRadialGradient(fx * w, fy * h, fr * m)
        a, z = QColor(col), QColor(col)
        a.setAlpha(alpha)
        z.setAlpha(0)
        g.setColorAt(0, a)
        g.setColorAt(1, z)
        p.fillRect(QRectF(0, 0, w, h), g)
    p.setClipping(False)
    p.setPen(QPen(border, border_w))
    p.drawPath(path)


# ---------------------------------------------------------------- spectrum analysis (pure Python, no numpy)
class Spectrum:
    """Collects decoded audio buffers and turns the audible moment into bar levels."""
    N = 512

    def __init__(self, bands=28):
        self.bands = bands
        self.buffers = deque()
        self.frames_kept = 0
        n = self.N
        self.win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
        bits = n.bit_length() - 1
        self.rev = [int(format(i, f"0{bits}b")[::-1], 2) for i in range(n)]
        self.cos = [math.cos(-2 * math.pi * k / n) for k in range(n // 2)]
        self.sin = [math.sin(-2 * math.pi * k / n) for k in range(n // 2)]
        self._edges = {}

    def clear(self):
        self.buffers.clear()
        self.frames_kept = 0

    def push(self, buf):
        f = buf.format()
        ch, rate, sf = f.channelCount(), f.sampleRate(), f.sampleFormat()
        SF = QAudioFormat.SampleFormat
        off = 0
        if sf == SF.Int16:
            arr, scale = array.array("h"), 1 / 32768
        elif sf == SF.Float:
            arr, scale = array.array("f"), 1.0
        elif sf == SF.Int32:
            arr, scale = array.array("i"), 1 / 2147483648
        elif sf == SF.UInt8:
            arr, scale, off = array.array("B"), 1 / 128, 128
        else:
            return
        if ch < 1 or rate < 1:
            return
        raw = bytes(buf.constData())
        arr.frombytes(raw[:len(raw) // arr.itemsize * arr.itemsize])
        self.buffers.append((buf.startTime(), rate, ch, scale, off, arr))
        self.frames_kept += len(arr) // ch
        while self.frames_kept > rate * 3 and len(self.buffers) > 1:  # keep ~3 seconds
            old = self.buffers.popleft()
            self.frames_kept -= len(old[5]) // old[2]

    def _band_edges(self, rate):
        if rate not in self._edges:
            hz = rate / self.N
            fmin, fmax = 40.0, min(16000.0, rate / 2 * 0.95)
            bins = [max(1, int(fmin * (fmax / fmin) ** (i / self.bands) / hz)) for i in range(self.bands + 1)]
            for i in range(1, len(bins)):
                bins[i] = max(bins[i], bins[i - 1] + 1)
            self._edges[rate] = bins
        return self._edges[rate]

    def _fft_mag(self, x):
        n = self.N
        re = [x[self.rev[i]] for i in range(n)]
        im = [0.0] * n
        size = 2
        while size <= n:
            half, step = size // 2, n // size
            for start in range(0, n, size):
                k = 0
                for j in range(start, start + half):
                    wr, wi = self.cos[k], self.sin[k]
                    xr = re[j + half] * wr - im[j + half] * wi
                    xi = re[j + half] * wi + im[j + half] * wr
                    re[j + half] = re[j] - xr
                    im[j + half] = im[j] - xi
                    re[j] += xr
                    im[j] += xi
                    k += step
            size *= 2
        return [math.hypot(re[i], im[i]) for i in range(n // 2)]

    def levels_at(self, pos_us):
        bufs = list(self.buffers)
        if not bufs:
            return None
        N = self.N
        pick, idx = None, 0
        for i, (start, rate, ch, _, _, arr) in enumerate(bufs):
            if start < 0:
                continue
            frames = len(arr) // ch
            if start <= pos_us < start + frames * 1_000_000 / rate:
                pick, idx = i, int((pos_us - start) * rate / 1_000_000)
                break
        if pick is None:  # playback position outside what we hold: use the closest edge
            valid = [i for i, b in enumerate(bufs) if b[0] >= 0]
            if valid and pos_us < bufs[valid[0]][0]:
                pick, idx = valid[0], 0
            else:
                pick = valid[-1] if valid else len(bufs) - 1
                idx = max(0, len(bufs[pick][5]) // bufs[pick][2] - N)
        rate = bufs[pick][1]
        mono = []
        j = pick
        while len(mono) < N and j < len(bufs):
            _, _, c, sc, of, a = bufs[j]
            take = min(N - len(mono), len(a) // c - idx)
            if take > 0:
                if c == 1:
                    mono.extend((x - of) * sc for x in a[idx:idx + take])
                else:
                    left = a[idx * c:(idx + take) * c:c]
                    right = a[idx * c + 1:(idx + take) * c:c]
                    mono.extend(((x + y) * 0.5 - of) * sc for x, y in zip(left, right))
            idx = 0
            j += 1
        if len(mono) < N:
            mono.extend([0.0] * (N - len(mono)))
        mags = self._fft_mag([m * w for m, w in zip(mono, self.win)])
        edges = self._band_edges(rate)
        out = []
        for i in range(self.bands):
            lo, hi = edges[i], min(edges[i + 1], len(mags))
            m = max(mags[lo:hi]) if hi > lo else 0.0
            db = 20 * math.log10(m / (N / 4) + 1e-6)
            lvl = (db + 58) / 58
            lvl *= 0.85 + 0.3 * i / self.bands
            out.append(min(1.0, max(0.0, lvl)))
        return out


# ---------------------------------------------------------------- widgets
class GlassCard(QFrame):
    """Frosted panel: translucent fill, soft highlight, light border."""

    def paintEvent(self, _):
        th = getattr(self.window(), "theme", None) or THEMES["Haze"]
        f0, f1 = (150, 70) if th["light"] else (52, 16)
        e0, e1, e2 = (235, 120, 190) if th["light"] else (140, 35, 80)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)
        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        fill.setColorAt(0, QColor(255, 255, 255, f0))
        fill.setColorAt(1, QColor(255, 255, 255, f1))
        p.fillPath(path, fill)
        edge = QLinearGradient(r.topLeft(), r.bottomRight())
        edge.setColorAt(0, QColor(255, 255, 255, e0))
        edge.setColorAt(0.5, QColor(255, 255, 255, e1))
        edge.setColorAt(1, QColor(255, 255, 255, e2))
        p.setPen(QPen(edge, 1.2))
        p.drawPath(path)


class ClickSlider(QSlider):
    """Slider that jumps to the clicked position."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                               int(e.position().x()), self.width())
            self.setValue(v)
            self.sliderMoved.emit(v)
        super().mousePressEvent(e)


class TitleBar(QWidget):
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()


class ReorderList(QListWidget):
    """Playlist: drag rows to reorder, and still accepts audio files dropped from Explorer."""
    reordered = Signal()
    filesDropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        else:
            super().dropEvent(e)
            self.reordered.emit()


class Visualizer(QWidget):
    """Spectrum bars drawn over the lower part of the cover art."""
    BARS = 28

    def __init__(self, parent, app_win):
        super().__init__(parent)
        self.app_win = app_win
        self.levels = [0.0] * self.BARS
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        if max(self.levels) < 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 28, 28)
        p.setClipPath(clip)
        scrim = QLinearGradient(0, h * 0.45, 0, h)
        scrim.setColorAt(0, QColor(0, 0, 0, 0))
        scrim.setColorAt(1, QColor(0, 0, 0, 115))
        p.fillRect(self.rect(), scrim)
        a = QColor(self.app_win.theme["acc"][0])
        n, gap, pad = self.BARS, 3, 14
        bw = (w - 2 * pad - gap * (n - 1)) / n
        maxh = h * 0.42
        p.setPen(Qt.NoPen)
        for i, lv in enumerate(self.levels):
            bh = max(3.0, lv * maxh)
            x, y = pad + i * (bw + gap), h - 14 - bh
            g = QLinearGradient(0, y + bh, 0, y)
            g.setColorAt(0, a)
            g.setColorAt(1, QColor(255, 255, 255, 235))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(x, y, bw, bh), bw / 2, bw / 2)


class MiniPlayer(QWidget):
    """Small always-on-top glass bar."""

    @property
    def theme(self):  # lets IconButton read the active theme from its window
        return self.app_win.theme

    def __init__(self, app_win):
        super().__init__()
        self.app_win = app_win
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 96)
        self.progress = 0.0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 10, 14, 18)
        lay.setSpacing(8)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.title = QLabel("Nothing playing")
        self.title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.artist = QLabel("")
        self.artist.setObjectName("muted")
        col.addStretch()
        col.addWidget(self.title)
        col.addWidget(self.artist)
        col.addStretch()
        lay.addLayout(col, 1)
        self.b_prev = IconButton("prev", 36, tip="Previous")
        self.b_play = IconButton("play", 48, primary=True, tip="Play / Pause")
        self.b_next = IconButton("next", 36, tip="Next")
        self.b_open = IconButton("expand", 30, tip="Back to full player")
        self.b_quit = IconButton("close", 30, danger=True, tip="Quit")
        for b in (self.b_prev, self.b_play, self.b_next, self.b_open, self.b_quit):
            lay.addWidget(b, 0, Qt.AlignVCenter)

    def set_text(self, title, artist):
        fm = QFontMetrics(self.title.font())
        self.title.setText(fm.elidedText(title, Qt.ElideRight, 158))
        self.title.setToolTip(title)
        self.artist.setText(QFontMetrics(self.artist.font()).elidedText(artist, Qt.ElideRight, 158))

    def set_playing(self, on):
        self.b_play.setKind("pause" if on else "play")

    def set_progress(self, pos, dur):
        self.progress = pos / dur if dur > 0 else 0.0
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        self.app_win.show_main()

    def paintEvent(self, _):
        th = self.app_win.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        border = QColor(255, 255, 255, 200 if th["light"] else 70)
        paint_backdrop(p, w, h, 26, th, self.app_win.blob_cols, border)
        track = QColor(0, 0, 0, 35) if th["light"] else QColor(255, 255, 255, 45)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(20, h - 13, w - 34, 3), 1.5, 1.5)
        if self.progress > 0:
            g = QLinearGradient(20, 0, w - 14, 0)
            g.setColorAt(0, QColor(th["acc"][0]))
            g.setColorAt(1, QColor(th["acc"][1]))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(20, h - 13, (w - 34) * min(1.0, self.progress), 3), 1.5, 1.5)


class MediaKeys(QAbstractNativeEventFilter):
    """System-wide media keys on Windows (RegisterHotKey). Inert elsewhere."""
    WM_HOTKEY = 0x0312

    def __init__(self, actions):
        super().__init__()
        self.actions = actions  # {virtual-key code: callable}
        self.ids = {}

    def register(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
        except Exception:
            return False
        for n, vk in enumerate(self.actions, start=1):
            if user32.RegisterHotKey(None, n, 0x4000, vk):  # MOD_NOREPEAT
                self.ids[n] = vk
        return bool(self.ids)

    def unregister(self):
        try:
            import ctypes
            for n in self.ids:
                ctypes.windll.user32.UnregisterHotKey(None, n)
        except Exception:
            pass
        self.ids = {}

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) == b"windows_generic_MSG":
                import ctypes.wintypes as wt
                msg = wt.MSG.from_address(int(message))
                if msg.message == self.WM_HOTKEY and msg.wParam in self.ids:
                    QTimer.singleShot(0, self.actions[self.ids[msg.wParam]])
                    return True, 0
        except Exception:
            pass
        return False, 0


# ---------------------------------------------------------------- main window
class HazeAudio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(980, 640)
        self.setMinimumSize(800, 560)

        self.theme_name = "Haze"
        self.theme = THEMES["Haze"]
        self.blob_cols = [QColor(c) for c in self.theme["blobs"]]
        self.blob_from = list(self.blob_cols)
        self.blob_to = list(self.blob_cols)
        self.blob_anim = QVariantAnimation(self)
        self.blob_anim.setDuration(700)
        self.blob_anim.setStartValue(0.0)
        self.blob_anim.setEndValue(1.0)
        self.blob_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.blob_anim.valueChanged.connect(self._blob_step)

        self.audio = QAudioOutput()
        self.audio.setVolume(0.8)
        self.media = QMediaPlayer()
        self.media.setAudioOutput(self.audio)
        self.device_hex = None
        self.fade = 1.0
        self._fade_cb = None
        self._pausing = False
        self.fade_anim = QVariantAnimation(self)
        self.fade_anim.valueChanged.connect(self._on_fade)
        self.fade_anim.finished.connect(self._fade_finished)

        self.spectrum = Spectrum(Visualizer.BARS)
        self.tap = None
        if QAudioBufferOutput is not None:
            try:
                self.tap = QAudioBufferOutput(self)
                self.media.setAudioBufferOutput(self.tap)
                self.tap.audioBufferReceived.connect(self.on_audio_buffer)
            except Exception:
                self.tap = None
        self.viz_on = True
        self.viz_timer = QTimer(self)
        self.viz_timer.setInterval(40)
        self.viz_timer.timeout.connect(self.viz_tick)

        self.query = ""
        self.paths: list[str] = []
        self.cur = -1
        self.cur_path = None
        self.shuffle = False
        self.repeat = 0  # 0 off, 1 all, 2 one
        self.drag_over = False
        self.scrubbing = False
        self.pending_seek = None
        self.cover_img = None
        self.cover_colors_on = True
        self.close_to_tray = True
        self.global_keys = True
        self.media_keys = None
        self.tray_hint_shown = False
        self.quitting = False
        self.sleep_minutes = 0
        self.sleep_timer = QTimer(self)
        self.sleep_timer.setSingleShot(True)
        self.sleep_timer.timeout.connect(self._sleep_now)

        self._build()
        self.mini = MiniPlayer(self)
        self._build_tray()
        self._wire()
        self.apply_theme("Haze", instant=True)
        self.refresh_empty()
        self.start_server()
        self.load_state()
        self.apply_global_keys()

    # ---------- UI ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 16)
        root.setSpacing(12)

        bar = TitleBar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 0, 0, 0)
        bl.setSpacing(6)
        name = QLabel(APP_NAME)
        name.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.btn_mini = IconButton("mini", 30, tip="Mini player")
        self.btn_gear = IconButton("gear", 30, tip="Settings")
        self.btn_pin = IconButton("pin", 30, checkable=True, tip="Keep on top")
        self.btn_min = IconButton("min", 30, tip="Minimize")
        self.btn_close = IconButton("close", 30, danger=True, tip="Close")
        bl.addWidget(name)
        bl.addStretch()
        for b in (self.btn_mini, self.btn_gear, self.btn_pin, self.btn_min, self.btn_close):
            bl.addWidget(b)
        root.addWidget(bar)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        left = GlassCard()
        left.setFixedWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(22, 22, 22, 20)
        lv.setSpacing(6)
        self.cover = QLabel()
        self.cover.setFixedSize(COVER, COVER)
        self.viz = Visualizer(self.cover, self)
        self.viz.setGeometry(0, 0, COVER, COVER)
        lv.addWidget(self.cover, 0, Qt.AlignHCenter)
        lv.addSpacing(8)
        self.title = QLabel("Nothing playing")
        self.title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.artist = QLabel("Drop music to get started")
        self.artist.setObjectName("muted")
        self.artist.setAlignment(Qt.AlignCenter)
        lv.addWidget(self.title)
        lv.addWidget(self.artist)
        lv.addSpacing(6)

        seek_row = QHBoxLayout()
        self.t_cur = QLabel("00:00")
        self.t_cur.setObjectName("muted")
        self.t_tot = QLabel("00:00")
        self.t_tot.setObjectName("muted")
        self.seek = ClickSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        seek_row.addWidget(self.t_cur)
        seek_row.addWidget(self.seek, 1)
        seek_row.addWidget(self.t_tot)
        lv.addLayout(seek_row)

        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.b_shuf = IconButton("shuffle", 40, checkable=True, tip="Shuffle")
        self.b_prev = IconButton("prev", 46, tip="Previous")
        self.b_play = IconButton("play", 70, primary=True, tip="Play / Pause (Space)")
        self.b_next = IconButton("next", 46, tip="Next")
        self.b_rep = IconButton("repeat", 40, checkable=True, tip="Repeat: off")
        ctl.addStretch()
        for w in (self.b_shuf, self.b_prev, self.b_play, self.b_next, self.b_rep):
            ctl.addWidget(w, 0, Qt.AlignVCenter)
        ctl.addStretch()
        lv.addLayout(ctl)

        vol_row = QHBoxLayout()
        vol_lbl = QLabel("Volume")
        vol_lbl.setObjectName("muted")
        self.vol = ClickSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self.vol, 1)
        lv.addLayout(vol_row)
        body.addWidget(left)

        right = GlassCard()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(22, 20, 14, 18)
        rv.setSpacing(10)
        head = QHBoxLayout()
        h = QLabel("Playlist")
        h.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.count = QLabel("0 tracks")
        self.count.setObjectName("muted")
        self.b_add = QPushButton("Add files")
        self.b_more = QPushButton("⋯")
        self.b_more.setToolTip("Open / save playlist, sort")
        self.b_clear = QPushButton("Clear")
        for b in (self.b_add, self.b_more, self.b_clear):
            b.setObjectName("pill")
            b.setFixedHeight(32)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        head.addWidget(h)
        head.addWidget(self.count)
        head.addStretch()
        head.addWidget(self.b_add)
        head.addWidget(self.b_more)
        head.addWidget(self.b_clear)
        head.setContentsMargins(0, 0, 8, 0)
        rv.addLayout(head)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search playlist  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        sr = QHBoxLayout()
        sr.setContentsMargins(0, 0, 8, 0)
        sr.addWidget(self.search)
        rv.addLayout(sr)
        self.empty = QLabel("Drag and drop audio files or folders anywhere in this window\n"
                            "MP3 · WAV · OGG · FLAC · M4A · AAC · Opus")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignCenter)
        self.list = ReorderList()
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        rv.addWidget(self.empty, 1)
        rv.addWidget(self.list, 1)
        body.addWidget(right, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(6, 0, 0, 0)
        self.credit = QLabel()
        self.credit.setObjectName("muted")
        self.credit.setTextFormat(Qt.RichText)
        self.credit.setOpenExternalLinks(True)
        self.credit.setToolTip("github.com/Pabelic1221")
        foot.addWidget(self.credit)
        foot.addStretch()
        root.addLayout(foot)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QIcon(resource_path("icon.ico"))
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        menu.addAction("Show HazeAudio", self.show_main)
        menu.addAction("Play / Pause", self.toggle)
        menu.addAction("Next", lambda: self.step(1))
        menu.addAction("Previous", self.prev)
        menu.addAction("Mini player", self.enter_mini)
        menu.addSeparator()
        menu.addAction("Quit", self.quit_app)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_click)
        self.tray.setToolTip(APP_NAME)
        self.tray.show()

    def _wire(self):
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close.clicked.connect(self.close)
        self.btn_pin.toggled.connect(self.set_on_top)
        self.btn_mini.clicked.connect(self.enter_mini)
        self.btn_gear.clicked.connect(self.show_settings)
        self.b_play.clicked.connect(self.toggle)
        self.b_next.clicked.connect(lambda: self.step(1))
        self.b_prev.clicked.connect(self.prev)
        self.b_shuf.toggled.connect(lambda v: setattr(self, "shuffle", v))
        self.b_rep.clicked.connect(self.cycle_repeat)
        self.b_add.clicked.connect(self.pick_files)
        self.b_more.clicked.connect(self.show_playlist_menu)
        self.b_clear.clicked.connect(self.clear)
        self.search.textChanged.connect(self.apply_filter)
        self.list.itemDoubleClicked.connect(lambda it: self.play_index(self.list.row(it)))
        self.list.customContextMenuRequested.connect(self.list_menu)
        self.list.reordered.connect(self.sync_paths)
        self.list.filesDropped.connect(self.on_files_dropped)
        self.vol.valueChanged.connect(lambda _: self._apply_volume())
        self.seek.sliderPressed.connect(lambda: setattr(self, "scrubbing", True))
        self.seek.sliderReleased.connect(lambda: setattr(self, "scrubbing", False))
        self.seek.sliderMoved.connect(self.media.setPosition)
        self.media.positionChanged.connect(self.on_pos)
        self.media.durationChanged.connect(self.on_dur)
        self.media.playbackStateChanged.connect(self.on_state)
        self.media.mediaStatusChanged.connect(self.on_status)
        self.media.metaDataChanged.connect(self.on_meta)
        self.media.errorOccurred.connect(lambda *_: self.artist.setText("Can't play this file"))
        self.mini.b_play.clicked.connect(self.toggle)
        self.mini.b_next.clicked.connect(lambda: self.step(1))
        self.mini.b_prev.clicked.connect(self.prev)
        self.mini.b_open.clicked.connect(self.show_main)
        self.mini.b_quit.clicked.connect(self.quit_app)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle)
        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self.media.setPosition(max(0, self.media.position() - 5000)))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self.media.setPosition(self.media.position() + 5000))
        QShortcut(QKeySequence(Qt.Key_Up), self, lambda: self.vol.setValue(self.vol.value() + 5))
        QShortcut(QKeySequence(Qt.Key_Down), self, lambda: self.vol.setValue(self.vol.value() - 5))
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.remove_selected)
        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_search)
        QShortcut(QKeySequence(Qt.Key_MediaTogglePlayPause), self, self.toggle)
        QShortcut(QKeySequence(Qt.Key_MediaNext), self, lambda: self.step(1))
        QShortcut(QKeySequence(Qt.Key_MediaPrevious), self, self.prev)

    # ---------- theme & colors ----------
    def apply_theme(self, name, instant=False):
        if name not in THEMES:
            name = "Haze"
        self.theme_name, self.theme = name, THEMES[name]
        css = build_style(self.theme)
        self.setStyleSheet(css)
        self.mini.setStyleSheet(css)
        pal = self.search.palette()
        ph = QColor("#1f1b3d" if self.theme["light"] else "#ffffff")
        ph.setAlpha(120)
        pal.setColor(QPalette.PlaceholderText, ph)
        self.search.setPalette(pal)
        link = self.theme["acc"][0] if self.theme["light"] else "#ffd6ee"
        self.credit.setText(f'Made with ❤️ by <a href="{CREDIT_URL}" '
                            f'style="color:{link}; text-decoration:none;">Jushua Pabelic</a>')
        self.set_cover(self.cover_img, instant=instant)
        for btn in self.findChildren(IconButton) + self.mini.findChildren(IconButton):
            btn.update()
        self.update()
        self.mini.update()

    def set_cover(self, img, instant=False):
        self.cover_img = img if (isinstance(img, QImage) and not img.isNull()) else None
        a, b = self.theme["acc"]
        self.cover.setPixmap(make_cover(self.cover_img, a, b))
        target = [QColor(c) for c in self.theme["blobs"]]
        if self.cover_colors_on and self.cover_img is not None:
            target = dominant_colors(self.cover_img) or target
        if self.theme["light"]:
            target = [lerp_color(c, QColor("#ffffff"), 0.35) for c in target]
        self.blob_from = [QColor(c) for c in self.blob_cols]
        self.blob_to = target
        self.blob_anim.stop()
        if instant:
            self._blob_step(1.0)
        else:
            self.blob_anim.start()

    def _blob_step(self, t):
        t = float(t)
        self.blob_cols = [lerp_color(f, g, t) for f, g in zip(self.blob_from, self.blob_to)]
        self.update()
        if self.mini.isVisible():
            self.mini.update()

    def set_cover_colors(self, on):
        self.cover_colors_on = bool(on)
        self.set_cover(self.cover_img)

    # ---------- painting ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.drag_over:
            border, bw = QColor(255, 255, 255, 220), 3
        else:
            border, bw = QColor(255, 255, 255, 200 if self.theme["light"] else 55), 1.5
        paint_backdrop(p, self.width(), self.height(), 30, self.theme, self.blob_cols, border, bw)

    def resizeEvent(self, e):
        self.grip.move(self.width() - 26, self.height() - 26)
        super().resizeEvent(e)

    # ---------- drag and drop ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.drag_over = True
            self.update()

    def dragLeaveEvent(self, _):
        self.drag_over = False
        self.update()

    def dropEvent(self, e):
        self.on_files_dropped([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def on_files_dropped(self, paths):
        self.drag_over = False
        self.update()
        self.add_paths(paths)

    # ---------- playlist ----------
    def pick_files(self):
        exts = " ".join(f"*{x}" for x in sorted(AUDIO_EXT | PLAYLIST_EXT))
        files, _ = QFileDialog.getOpenFileNames(self, "Add audio files", "", f"Audio ({exts});;All files (*)")
        self.add_paths(files)

    def add_paths(self, raw, autoplay=True, force=False):
        expanded = []
        for r in raw:
            if Path(r).suffix.lower() in PLAYLIST_EXT and os.path.isfile(r):
                expanded += read_m3u(r)
            else:
                expanded.append(r)
        found = []
        for r in expanded:
            if os.path.isdir(r):
                for root_dir, _, names in os.walk(r):
                    found += [os.path.join(root_dir, n) for n in sorted(names)
                              if Path(n).suffix.lower() in AUDIO_EXT]
            elif os.path.isfile(r) and Path(r).suffix.lower() in AUDIO_EXT:
                found.append(r)
        if not found:
            if raw:
                self.artist.setText("No supported audio files in that drop")
            return
        known = {os.path.normcase(os.path.abspath(p)): i for i, p in enumerate(self.paths)}
        first_new = first_dup = None
        for f in found:
            key = os.path.normcase(os.path.abspath(f))
            if key in known:
                if first_dup is None:
                    first_dup = known[key]
                continue
            known[key] = len(self.paths)
            if first_new is None:
                first_new = len(self.paths)
            self._append_item(f)
        # play the first newly added track; if everything was already listed, "open with" plays that one
        target = first_new if first_new is not None else (first_dup if force else None)
        self.refresh_empty()
        if self.search.text().strip():
            self.apply_filter(self.search.text())
        if autoplay and target is not None and (self.cur < 0 or force):
            self.play_index(target)

    def _append_item(self, path):
        self.paths.append(path)
        it = QListWidgetItem(Path(path).stem)
        it.setData(Qt.UserRole, path)
        it.setToolTip(path)
        self.list.addItem(it)

    def refresh_empty(self):
        self.empty.setVisible(not self.paths)
        self.list.setVisible(bool(self.paths))
        self.update_count()

    def update_count(self):
        n, q = len(self.paths), self.query
        if q:
            vis = sum(1 for i in range(self.list.count()) if not self.list.item(i).isHidden())
            self.count.setText(f"{vis} of {n}")
        else:
            self.count.setText(f"{n} track{'s' if n != 1 else ''}")

    def apply_filter(self, text):
        q = text.strip().lower()
        self.query = q
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(q) and q not in Path(it.data(Qt.UserRole)).stem.lower())
        self.list.setDragEnabled(not q)  # reordering a filtered view would be confusing
        self.update_count()

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def refresh_marks(self):
        for i in range(self.list.count()):
            it = self.list.item(i)
            stem = Path(it.data(Qt.UserRole)).stem
            it.setText(("♪  " if i == self.cur else "") + stem)

    def sync_paths(self):
        """Rebuild self.paths from the visible order after a drag-reorder."""
        self.paths = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
        self.cur = self.paths.index(self.cur_path) if self.cur_path in self.paths else -1
        self.refresh_marks()

    def rebuild_list(self, paths):
        self.list.clear()
        self.paths = []
        for p in paths:
            self._append_item(p)
        self.sync_paths()
        self.refresh_empty()
        self.apply_filter(self.search.text())

    def sort_playlist(self):
        self.rebuild_list(sorted(self.paths, key=lambda p: Path(p).stem.lower()))

    def play_next_row(self, row):
        if self.cur < 0 or row == self.cur:
            return
        it = self.list.takeItem(row)
        cur_row = self.cur if row > self.cur else self.cur - 1
        self.list.insertItem(cur_row + 1, it)
        self.sync_paths()

    def remove_selected(self):
        row = self.list.currentRow()
        if row >= 0:
            self.remove_row(row)

    def remove_row(self, row):
        if not 0 <= row < len(self.paths):
            return
        was_cur = row == self.cur
        self.list.takeItem(row)
        self.paths.pop(row)
        if was_cur:
            self.media.stop()
            self.media.setSource(QUrl())
            self.cur, self.cur_path = -1, None
            self.reset_display()
            if self.paths:
                self.play_index(min(row, len(self.paths) - 1))
        elif row < self.cur:
            self.cur -= 1
        self.refresh_marks()
        self.refresh_empty()

    def clear(self):
        self.media.stop()
        self.media.setSource(QUrl())
        self.paths.clear()
        self.list.clear()
        self.cur, self.cur_path = -1, None
        self.reset_display()
        self.refresh_empty()

    def reset_display(self):
        self.set_track_text("Nothing playing", "Drop music to get started")
        self.set_cover(None)
        self.spectrum.clear()
        self.seek.setRange(0, 0)
        self.t_cur.setText("00:00")
        self.t_tot.setText("00:00")
        self.update_tray_tip()

    def list_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        row, path = self.list.row(it), it.data(Qt.UserRole)
        m = self._menu()
        self._act(m, "Play", lambda _=False: self.play_index(row))
        self._act(m, "Play next", lambda _=False: self.play_next_row(row),
                  enabled=self.cur >= 0 and row != self.cur)
        self._act(m, "Show in folder", lambda _=False: self.reveal(path))
        m.addSeparator()
        self._act(m, "Remove from playlist", lambda _=False: self.remove_row(row))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def reveal(self, path):
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def show_playlist_menu(self):
        m = self._menu()
        self._act(m, "Open playlist…", lambda _=False: self.open_playlist())
        self._act(m, "Save playlist…", lambda _=False: self.save_playlist(), enabled=bool(self.paths))
        m.addSeparator()
        self._act(m, "Sort A → Z", lambda _=False: self.sort_playlist(), enabled=len(self.paths) > 1)
        m.exec(self.b_more.mapToGlobal(QPoint(0, self.b_more.height() + 4)))

    def save_playlist(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save playlist", str(Path.home() / "HazeAudio.m3u8"),
                                            "Playlist (*.m3u8 *.m3u)")
        if not fn:
            return
        lines = ["#EXTM3U"]
        for p in self.paths:
            lines += [f"#EXTINF:-1,{Path(p).stem}", p]
        try:
            Path(fn).write_text("\n".join(lines) + "\n", "utf-8")
        except OSError:
            self.artist.setText("Couldn't save the playlist")

    def open_playlist(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open playlist", "", "Playlist (*.m3u8 *.m3u)")
        if fn:
            self.clear()
            self.add_paths(read_m3u(fn), force=True)

    # ---------- menus ----------
    def _menu(self, parent=None):
        m = QMenu(parent or self)
        m.setAttribute(Qt.WA_TranslucentBackground)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        return m

    def _act(self, menu, text, slot, checked=None, group=None, enabled=True):
        a = QAction(text.replace("&", "&&"), menu)
        if checked is not None:
            a.setCheckable(True)
            a.setChecked(checked)
        if group is not None:
            group.addAction(a)
        a.setEnabled(enabled)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def show_settings(self):
        m = self._menu()
        sub = self._menu(m)
        sub.setTitle("Theme")
        g = QActionGroup(sub)
        for n in THEMES:
            self._act(sub, n, lambda _=False, n=n: self.apply_theme(n), checked=n == self.theme_name, group=g)
        m.addMenu(sub)
        self._act(m, "Colors from album art", self.set_cover_colors, checked=self.cover_colors_on)
        self._act(m, "Spectrum visualizer", self.set_viz, checked=self.viz_on, enabled=self.tap is not None)

        sub = self._menu(m)
        sub.setTitle("Output device")
        g = QActionGroup(sub)
        self._act(sub, "System default", lambda _=False: self.set_device(None),
                  checked=self.device_hex is None, group=g)
        for d in QMediaDevices.audioOutputs():
            self._act(sub, d.description(), lambda _=False, d=d: self.set_device(d),
                      checked=bytes(d.id()).hex() == self.device_hex, group=g)
        m.addMenu(sub)

        sub = self._menu(m)
        sub.setTitle("Sleep timer")
        g = QActionGroup(sub)
        for mins in (0, 15, 30, 45, 60, 90):
            self._act(sub, "Off" if mins == 0 else f"{mins} minutes", lambda _=False, k=mins: self.set_sleep(k),
                      checked=mins == self.sleep_minutes, group=g)
        m.addMenu(sub)

        m.addSeparator()
        self._act(m, "Keep playing in tray when closed", self.set_close_to_tray,
                  checked=self.close_to_tray, enabled=self.tray is not None)
        if sys.platform == "win32":
            self._act(m, "Global media keys", self.set_global_keys, checked=self.global_keys)
        m.addSeparator()
        self._act(m, "Open settings folder", lambda _=False: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(DATA_DIR))))
        self._act(m, f"Quit {APP_NAME}", lambda _=False: self.quit_app())
        m.exec(self.btn_gear.mapToGlobal(QPoint(0, self.btn_gear.height() + 4)))

    def set_viz(self, on):
        self.viz_on = bool(on)
        if not on:
            self.viz.levels = [0.0] * Visualizer.BARS
            self.viz.update()
            self.spectrum.clear()

    def set_device(self, dev):
        if dev is None:
            self.audio.setDevice(QMediaDevices.defaultAudioOutput())
            self.device_hex = None
        else:
            self.audio.setDevice(dev)
            self.device_hex = bytes(dev.id()).hex()

    def set_sleep(self, minutes):
        self.sleep_minutes = minutes
        self.sleep_timer.stop()
        if minutes:
            self.sleep_timer.start(minutes * 60 * 1000)
        self.update_tray_tip()

    def _sleep_now(self):
        self.sleep_minutes = 0
        self._pausing = True
        self.fade_to(0.0, 10000, self._after_fade_out)  # gentle 10-second fade, then pause

    def set_close_to_tray(self, on):
        self.close_to_tray = bool(on)

    def set_global_keys(self, on):
        self.global_keys = bool(on)
        self.apply_global_keys()

    def apply_global_keys(self):
        if sys.platform != "win32":
            return
        app = QApplication.instance()
        if self.global_keys and self.media_keys is None:
            mk = MediaKeys({0xB3: self.toggle, 0xB0: lambda: self.step(1), 0xB1: self.prev,
                            0xB2: self.stop_playback})
            if mk.register():
                app.installNativeEventFilter(mk)
                self.media_keys = mk
        elif not self.global_keys and self.media_keys is not None:
            app.removeNativeEventFilter(self.media_keys)
            self.media_keys.unregister()
            self.media_keys = None

    # ---------- window modes, tray, single instance ----------
    def set_on_top(self, on):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if visible:
            self.show()

    def show_main(self):
        self.mini.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def enter_mini(self):
        if self.mini.isVisible():
            return
        g = self.geometry()
        self.mini.move(g.x() + g.width() - self.mini.width() - 24, g.y() + 24)
        self.mini.show()
        self.hide()

    def _tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_main()

    def update_tray_tip(self):
        if self.tray is not None:
            tip = self.title.text() if self.cur >= 0 else APP_NAME
            self.tray.setToolTip(f"{tip}\n{APP_NAME}" if self.cur >= 0 else APP_NAME)

    def start_server(self):
        QLocalServer.removeServer(SERVER_NAME)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._incoming)
        self.server.listen(SERVER_NAME)

    def _incoming(self):
        conn = self.server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(500)
        try:
            paths = json.loads(bytes(conn.readAll()).decode("utf-8"))
        except ValueError:
            paths = []
        conn.disconnectFromServer()
        if paths:
            self.add_paths(paths, force=True)
        self.show_main()

    def quit_app(self):
        self.quitting = True
        self.save_state()
        self.media.stop()
        if self.media_keys is not None:
            self.media_keys.unregister()
        self.mini.hide()
        if self.tray is not None:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        keep = (self.close_to_tray and self.tray is not None and not self.quitting
                and self.media.playbackState() != QMediaPlayer.StoppedState)
        if keep:  # music is still going: hide to the tray instead of quitting
            e.ignore()
            self.hide()
            self.save_state()
            if not self.tray_hint_shown:
                self.tray_hint_shown = True
                self.tray.showMessage(APP_NAME, "Still playing. Use the tray icon to bring it back or quit.",
                                      QSystemTrayIcon.Information, 3500)
            return
        self.quit_app()
        e.accept()

    def fade_in(self):
        self.setWindowOpacity(0.0)
        self._open_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._open_anim.setDuration(260)
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)
        self._open_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._open_anim.start()

    # ---------- playback ----------
    def _apply_volume(self):
        self.audio.setVolume(self.vol.value() / 100 * self.fade)

    def _on_fade(self, v):
        self.fade = float(v)
        self._apply_volume()

    def _fade_finished(self):
        cb, self._fade_cb = self._fade_cb, None
        if cb:
            cb()

    def fade_to(self, target, ms, done=None):
        self._fade_cb = None
        self.fade_anim.stop()
        self._fade_cb = done
        self.fade_anim.setDuration(ms)
        self.fade_anim.setStartValue(float(self.fade))
        self.fade_anim.setEndValue(float(target))
        self.fade_anim.start()

    def _after_fade_out(self):
        if self.fade < 0.02:
            self.media.pause()
        self._pausing = False

    def play_index(self, i):
        if not 0 <= i < len(self.paths):
            return
        self.cur, self.cur_path, self.pending_seek = i, self.paths[i], None
        self.spectrum.clear()
        self.fade_anim.stop()
        self._pausing = False
        self.fade = 1.0
        self._apply_volume()
        self.media.setSource(QUrl.fromLocalFile(self.paths[i]))
        self.media.play()
        self.set_track_text(Path(self.paths[i]).stem, "Unknown artist")
        self.set_cover(None)
        self.list.setCurrentRow(i)
        self.refresh_marks()
        self.update_tray_tip()

    def select_without_play(self, i, position=0):
        self.cur, self.cur_path = i, self.paths[i]
        self.pending_seek = position or None
        self.media.setSource(QUrl.fromLocalFile(self.paths[i]))
        self.set_track_text(Path(self.paths[i]).stem, "Press play to continue")
        self.list.setCurrentRow(i)
        self.refresh_marks()
        self.update_tray_tip()

    def set_track_text(self, title, artist):
        self.title.setText(title)
        self.artist.setText(artist)
        self.mini.set_text(title, artist)

    def toggle(self):
        if self.cur < 0:
            if self.paths:
                self.play_index(0)
            return
        if self.media.playbackState() == QMediaPlayer.PlayingState:
            if self._pausing:  # clicked again mid-fade: change of mind, keep playing
                self._pausing = False
                self.fade_to(1.0, 200)
            else:
                self._pausing = True
                self.fade_to(0.0, 160, self._after_fade_out)
        else:
            self.fade_anim.stop()
            self._pausing = False
            self.fade = 0.0
            self._apply_volume()
            self.media.play()
            self.fade_to(1.0, 260)

    def stop_playback(self):
        self.fade_anim.stop()
        self.fade = 1.0
        self._apply_volume()
        self.media.stop()

    def step(self, d, auto=False):
        n = len(self.paths)
        if not n:
            return
        if self.shuffle and n > 1:
            nxt = random.choice([i for i in range(n) if i != self.cur])
        else:
            nxt = self.cur + d
            if nxt >= n:
                if self.repeat == 1 or not auto:
                    nxt = 0
                else:
                    self.media.stop()
                    return
            nxt %= n
        self.play_index(nxt)

    def prev(self):
        if self.media.position() > 3000:
            self.media.setPosition(0)
        else:
            self.step(-1)

    def cycle_repeat(self):
        self.set_repeat((self.repeat + 1) % 3)

    def set_repeat(self, mode):
        self.repeat = mode
        self.b_rep.setChecked(self.repeat > 0)
        self.b_rep.setKind("repeat1" if self.repeat == 2 else "repeat")
        self.b_rep.setToolTip(["Repeat: off", "Repeat: all", "Repeat: one track"][self.repeat])

    # ---------- media signals ----------
    def on_pos(self, ms):
        self.t_cur.setText(fmt(ms))
        if not self.scrubbing:
            self.seek.setValue(ms)
        if self.mini.isVisible():
            self.mini.set_progress(ms, self.media.duration())

    def on_dur(self, ms):
        self.seek.setRange(0, ms)
        self.t_tot.setText(fmt(ms))

    def on_state(self, st):
        playing = st == QMediaPlayer.PlayingState
        self.b_play.setKind("pause" if playing else "play")
        self.mini.set_playing(playing)
        if playing and not self.viz_timer.isActive():
            self.viz_timer.start()

    def on_status(self, st):
        if st in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia) and self.pending_seek:
            self.media.setPosition(self.pending_seek)
            self.pending_seek = None
        if st == QMediaPlayer.EndOfMedia:
            if self.repeat == 2:
                self.media.setPosition(0)
                self.media.play()
            else:
                self.step(1, auto=True)

    def on_meta(self):
        md = self.media.metaData()
        K = QMediaMetaData.Key
        title = md.stringValue(K.Title)
        artist = md.stringValue(K.ContributingArtist) or md.stringValue(K.AlbumArtist)
        if title or artist:
            self.set_track_text(title or self.title.text(), artist or self.artist.text())
            self.update_tray_tip()
        img = md.value(K.CoverArtImage) or md.value(K.ThumbnailImage)
        if isinstance(img, QImage) and not img.isNull():
            self.set_cover(img)

    # ---------- visualizer ----------
    def on_audio_buffer(self, buf):
        if not self.viz_on:
            return
        try:
            self.spectrum.push(buf)
        except Exception:
            pass

    def viz_tick(self):
        playing = self.media.playbackState() == QMediaPlayer.PlayingState
        target = None
        if playing and self.viz_on:
            try:
                target = self.spectrum.levels_at(self.media.position() * 1000)
            except Exception:
                target = None
        lv = self.viz.levels
        for i in range(len(lv)):
            t = target[i] if target else 0.0
            lv[i] = t if t > lv[i] else lv[i] * 0.84 + t * 0.16
        self.viz.update()
        if not playing and max(lv) < 0.01:
            self.viz_timer.stop()

    # ---------- saved session ----------
    def load_state(self):
        try:
            s = json.loads(STATE_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            return
        try:
            self.cover_colors_on = bool(s.get("cover_colors", True))
            self.viz_on = bool(s.get("visualizer", True)) and self.tap is not None
            self.close_to_tray = bool(s.get("close_to_tray", True))
            self.global_keys = bool(s.get("global_keys", True))
            self.apply_theme(s.get("theme", "Haze"), instant=True)
            self.vol.setValue(int(s.get("volume", 80)))
            self.b_shuf.setChecked(bool(s.get("shuffle", False)))
            self.set_repeat(int(s.get("repeat", 0)) % 3)
            hexid = s.get("device")
            if hexid:
                for d in QMediaDevices.audioOutputs():
                    if bytes(d.id()).hex() == hexid:
                        self.set_device(d)
                        break
            x, y, w, h = s.get("geometry", (0, 0, 0, 0))
            if (w >= self.minimumWidth() and h >= self.minimumHeight()
                    and QGuiApplication.screenAt(QPoint(x + 60, y + 20))):
                self.setGeometry(x, y, w, h)
            if s.get("on_top"):
                self.btn_pin.setChecked(True)
            paths = [p for p in s.get("paths", []) if os.path.isfile(p)]
            if paths:
                self.add_paths(paths, autoplay=False)
                last = s.get("current_path")
                if last in self.paths:
                    self.select_without_play(self.paths.index(last), int(s.get("position", 0)))
        except (TypeError, ValueError):
            pass

    def save_state(self):
        g = self.geometry()
        state = {
            "volume": self.vol.value(), "shuffle": self.shuffle, "repeat": self.repeat,
            "on_top": self.btn_pin.isChecked(), "theme": self.theme_name,
            "cover_colors": self.cover_colors_on, "visualizer": self.viz_on,
            "close_to_tray": self.close_to_tray, "global_keys": self.global_keys,
            "device": self.device_hex,
            "geometry": [g.x(), g.y(), g.width(), g.height()],
            "paths": self.paths,
            "current_path": self.paths[self.cur] if 0 <= self.cur < len(self.paths) else None,
            "position": self.media.position(),
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
            tmp.replace(STATE_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    install_crash_log()
    if sys.platform == "win32":
        try:  # lets Windows show our icon on the taskbar instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HazeAudio.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # the tray keeps the app alive when the window is hidden
    args = [os.path.abspath(a) for a in sys.argv[1:]]
    if send_to_running(args):  # already open: pass files over and exit
        sys.exit(0)
    icon = resource_path("icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    app.setFont(QFont("Segoe UI", 10))
    win = HazeAudio()
    win.show()
    win.fade_in()
    if args:
        win.add_paths(args, force=True)
    sys.exit(app.exec())
