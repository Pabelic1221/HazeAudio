"""
HazeAudio - a drag-and-drop audio player with a glassmorphism UI.

Install:  pip install PySide6
Run:      python haze_audio.py

Shortcuts: Space play/pause | Left/Right seek 5s | Up/Down volume | Delete remove track
"""
import json
import os
import random
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QIcon, QImage, QKeySequence,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QShortcut)
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QSizeGrip, QSlider,
                               QStyle, QVBoxLayout, QWidget)

AUDIO_EXT = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".opus", ".wma", ".weba"}
COVER = 250
APP_NAME = "HazeAudio"
DATA_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "HazeAudio"
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "error.log"
SERVER_NAME = "HazeAudio-single-instance"


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

STYLE = """
QLabel { color: white; background: transparent; }
QLabel#muted { color: rgba(255,255,255,0.62); }
QPushButton { color: white; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
              border-radius: 22px; font-size: 15px; }
QPushButton:hover { background: rgba(255,255,255,0.24); }
QPushButton:pressed { background: rgba(255,255,255,0.08); }
QPushButton:checked { background: rgba(255,255,255,0.38); border-color: rgba(255,255,255,0.7); }
QPushButton:focus { outline: none; border-color: white; }
QPushButton#play { border: 1px solid rgba(255,255,255,0.5); border-radius: 32px; font-size: 22px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,100,180,0.85), stop:1 rgba(120,100,255,0.85)); }
QPushButton#play:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,130,200,1), stop:1 rgba(140,120,255,1)); }
QPushButton#pill { border-radius: 16px; padding: 0 14px; font-size: 12px; }
QPushButton#win { border-radius: 14px; font-size: 13px; }
QPushButton#close:hover { background: rgba(255,80,90,0.75); }
QSlider::groove:horizontal { height: 6px; background: rgba(255,255,255,0.18); border-radius: 3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff6fb5, stop:1 #8f7bff); border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: white; }
QListWidget { background: transparent; border: none; outline: none; color: white; font-size: 13px; }
QListWidget::item { padding: 10px 12px; border-radius: 12px; margin: 2px 0; }
QListWidget::item:hover { background: rgba(255,255,255,0.10); }
QListWidget::item:selected { background: rgba(255,255,255,0.22); color: white; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 4px 0; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.3); border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def fmt(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def make_cover(img: QImage | None) -> QPixmap:
    """Rounded cover art, or a gradient placeholder when the file has no artwork."""
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
        g.setColorAt(0, QColor(255, 110, 180, 200))
        g.setColorAt(1, QColor(90, 120, 255, 200))
        p.fillRect(0, 0, COVER, COVER, g)
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(QFont("Segoe UI", 80))
        p.drawText(QRectF(0, 0, COVER, COVER), Qt.AlignCenter, "♪")
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 90), 1.5))
    p.drawPath(clip)
    p.end()
    return pm


class GlassCard(QFrame):
    """Frosted panel: translucent fill, soft highlight, light border."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)
        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        fill.setColorAt(0, QColor(255, 255, 255, 52))
        fill.setColorAt(1, QColor(255, 255, 255, 16))
        p.fillPath(path, fill)
        edge = QLinearGradient(r.topLeft(), r.bottomRight())
        edge.setColorAt(0, QColor(255, 255, 255, 140))
        edge.setColorAt(0.5, QColor(255, 255, 255, 35))
        edge.setColorAt(1, QColor(255, 255, 255, 80))
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


class HazeAudio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HazeAudio")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(960, 600)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(STYLE)

        self.audio = QAudioOutput()
        self.audio.setVolume(0.8)
        self.media = QMediaPlayer()
        self.media.setAudioOutput(self.audio)
        self.paths: list[str] = []
        self.cur = -1
        self.shuffle = False
        self.repeat = 0  # 0 off, 1 all, 2 one
        self.drag_over = False
        self.scrubbing = False

        self._build()
        self._wire()
        self.set_cover(None)
        self.refresh_empty()
        self.start_server()
        self.load_state()

    # ---------- UI ----------
    def _btn(self, text, size=44, name=None, checkable=False, tip=""):
        b = QPushButton(text)
        b.setFixedSize(size, size)
        b.setCursor(Qt.PointingHandCursor)
        b.setCheckable(checkable)
        b.setToolTip(tip)
        b.setStyleSheet(f"QPushButton{{border-radius:{size // 2}px;}}")
        if name:
            b.setObjectName(name)
        return b

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 20)
        root.setSpacing(12)

        bar = TitleBar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 0, 0, 0)
        name = QLabel("HazeAudio")
        name.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.btn_min = self._btn("–", 28, "win", tip="Minimize")
        self.btn_pin = self._btn("📌", 28, "win", checkable=True, tip="Keep on top")
        self.btn_close = self._btn("✕", 28, "win", tip="Close")
        self.btn_close.setObjectName("close")
        self.btn_close.setStyleSheet("QPushButton{border-radius:14px;font-size:13px;}")
        bl.addWidget(name)
        bl.addStretch()
        bl.addWidget(self.btn_pin)
        bl.addWidget(self.btn_min)
        bl.addWidget(self.btn_close)
        root.addWidget(bar)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        # now playing
        left = GlassCard()
        left.setFixedWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(22, 22, 22, 20)
        lv.setSpacing(6)
        self.cover = QLabel()
        self.cover.setFixedSize(COVER, COVER)
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
        self.b_shuf = self._btn("⇄", 38, checkable=True, tip="Shuffle")
        self.b_prev = self._btn("⏮", 44, tip="Previous")
        self.b_play = self._btn("▶", 64, "play", tip="Play / Pause (Space)")
        self.b_next = self._btn("⏭", 44, tip="Next")
        self.b_rep = self._btn("↻", 38, checkable=True, tip="Repeat: off")
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

        # playlist
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
        self.b_clear = QPushButton("Clear")
        for b in (self.b_add, self.b_clear):
            b.setObjectName("pill")
            b.setFixedHeight(32)
            b.setCursor(Qt.PointingHandCursor)
        head.addWidget(h)
        head.addWidget(self.count)
        head.addStretch()
        head.addWidget(self.b_add)
        head.addWidget(self.b_clear)
        head.setContentsMargins(0, 0, 8, 0)
        rv.addLayout(head)
        self.empty = QLabel("Drag and drop audio files or folders anywhere in this window\n"
                            "MP3 · WAV · OGG · FLAC · M4A · AAC · Opus")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignCenter)
        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        rv.addWidget(self.empty, 1)
        rv.addWidget(self.list, 1)
        body.addWidget(right, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(6, 0, 0, 0)
        credit = QLabel('Made with ❤️ by <a href="https://github.com/Pabelic1221" '
                        'style="color:#ffd6ee; text-decoration:none;">Jushua Pabelic</a>')
        credit.setObjectName("muted")
        credit.setTextFormat(Qt.RichText)
        credit.setOpenExternalLinks(True)
        credit.setToolTip("github.com/Pabelic1221")
        foot.addWidget(credit)
        foot.addStretch()
        root.addLayout(foot)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)

    def _wire(self):
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close.clicked.connect(self.close)
        self.btn_pin.toggled.connect(self.set_on_top)
        self.b_play.clicked.connect(self.toggle)
        self.b_next.clicked.connect(lambda: self.step(1))
        self.b_prev.clicked.connect(self.prev)
        self.b_shuf.toggled.connect(lambda v: setattr(self, "shuffle", v))
        self.b_rep.clicked.connect(self.cycle_repeat)
        self.b_add.clicked.connect(self.pick_files)
        self.b_clear.clicked.connect(self.clear)
        self.list.itemDoubleClicked.connect(lambda it: self.play_index(self.list.row(it)))
        self.vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.seek.sliderPressed.connect(lambda: setattr(self, "scrubbing", True))
        self.seek.sliderReleased.connect(lambda: setattr(self, "scrubbing", False))
        self.seek.sliderMoved.connect(self.media.setPosition)
        self.media.positionChanged.connect(self.on_pos)
        self.media.durationChanged.connect(self.on_dur)
        self.media.playbackStateChanged.connect(self.on_state)
        self.media.mediaStatusChanged.connect(self.on_status)
        self.media.metaDataChanged.connect(self.on_meta)
        self.media.errorOccurred.connect(lambda *_: self.artist.setText("Can't play this file"))
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle)
        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self.media.setPosition(max(0, self.media.position() - 5000)))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self.media.setPosition(self.media.position() + 5000))
        QShortcut(QKeySequence(Qt.Key_Up), self, lambda: self.vol.setValue(self.vol.value() + 5))
        QShortcut(QKeySequence(Qt.Key_Down), self, lambda: self.vol.setValue(self.vol.value() - 5))
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.remove_selected)
        QShortcut(QKeySequence(Qt.Key_MediaTogglePlayPause), self, self.toggle)
        QShortcut(QKeySequence(Qt.Key_MediaNext), self, lambda: self.step(1))
        QShortcut(QKeySequence(Qt.Key_MediaPrevious), self, self.prev)

    # ---------- app behaviour: on-top, single instance, saved session ----------
    def set_on_top(self, on):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if visible:
            self.show()

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
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def select_without_play(self, i):
        self.cur = i
        self.media.setSource(QUrl.fromLocalFile(self.paths[i]))
        self.title.setText(Path(self.paths[i]).stem)
        self.artist.setText("Press play to continue")
        self.list.setCurrentRow(i)
        self.refresh_marks()

    def load_state(self):
        try:
            s = json.loads(STATE_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            return
        try:
            self.vol.setValue(int(s.get("volume", 80)))
            self.b_shuf.setChecked(bool(s.get("shuffle", False)))
            self.set_repeat(int(s.get("repeat", 0)) % 3)
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
                    self.select_without_play(self.paths.index(last))
        except (TypeError, ValueError):
            pass

    def save_state(self):
        g = self.geometry()
        state = {
            "volume": self.vol.value(), "shuffle": self.shuffle, "repeat": self.repeat,
            "on_top": self.btn_pin.isChecked(),
            "geometry": [g.x(), g.y(), g.width(), g.height()],
            "paths": self.paths,
            "current_path": self.paths[self.cur] if 0 <= self.cur < len(self.paths) else None,
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
            tmp.replace(STATE_FILE)
        except OSError:
            pass

    def closeEvent(self, e):
        self.save_state()
        self.media.stop()
        e.accept()

    # ---------- painting ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 30, 30)
        p.setClipPath(path)
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor("#1a1048"))
        bg.setColorAt(0.55, QColor("#2b1a70"))
        bg.setColorAt(1, QColor("#0d3a5e"))
        p.fillRect(self.rect(), bg)
        m = max(w, h)
        for fx, fy, fr, col in ((0.12, 0.18, 0.42, QColor(255, 79, 163)),
                                (0.88, 0.22, 0.38, QColor(56, 189, 248)),
                                (0.62, 0.95, 0.46, QColor(167, 139, 250)),
                                (0.08, 0.92, 0.30, QColor(34, 211, 238))):
            g = QRadialGradient(fx * w, fy * h, fr * m)
            c0, c1 = QColor(col), QColor(col)
            c0.setAlpha(150)
            c1.setAlpha(0)
            g.setColorAt(0, c0)
            g.setColorAt(1, c1)
            p.fillRect(self.rect(), g)
        p.setClipping(False)
        glow = 200 if self.drag_over else 55
        p.setPen(QPen(QColor(255, 255, 255, glow), 3 if self.drag_over else 1.5))
        p.drawPath(path)

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
        self.drag_over = False
        self.update()
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ---------- playlist ----------
    def pick_files(self):
        exts = " ".join(f"*{x}" for x in sorted(AUDIO_EXT))
        files, _ = QFileDialog.getOpenFileNames(self, "Add audio files", "", f"Audio ({exts});;All files (*)")
        self.add_paths(files)

    def add_paths(self, raw, autoplay=True, force=False):
        found = []
        for r in raw:
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
        first = len(self.paths)
        for f in found:
            self.paths.append(f)
            it = QListWidgetItem(Path(f).stem)
            it.setToolTip(f)
            self.list.addItem(it)
        self.refresh_empty()
        if autoplay and (self.cur < 0 or force):
            self.play_index(first)

    def refresh_empty(self):
        n = len(self.paths)
        self.count.setText(f"{n} track{'s' if n != 1 else ''}")
        self.empty.setVisible(n == 0)
        self.list.setVisible(n > 0)

    def refresh_marks(self):
        for i in range(self.list.count()):
            it = self.list.item(i)
            stem = Path(self.paths[i]).stem
            it.setText(("♪  " if i == self.cur else "") + stem)

    def remove_selected(self):
        row = self.list.currentRow()
        if row < 0:
            return
        was_cur = row == self.cur
        self.list.takeItem(row)
        self.paths.pop(row)
        if was_cur:
            self.media.stop()
            self.media.setSource(QUrl())
            self.cur = -1
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
        self.cur = -1
        self.reset_display()
        self.refresh_empty()

    def reset_display(self):
        self.title.setText("Nothing playing")
        self.artist.setText("Drop music to get started")
        self.set_cover(None)
        self.seek.setRange(0, 0)
        self.t_cur.setText("00:00")
        self.t_tot.setText("00:00")

    # ---------- playback ----------
    def play_index(self, i):
        if not 0 <= i < len(self.paths):
            return
        self.cur = i
        self.media.setSource(QUrl.fromLocalFile(self.paths[i]))
        self.media.play()
        self.title.setText(Path(self.paths[i]).stem)
        self.artist.setText("Unknown artist")
        self.set_cover(None)
        self.list.setCurrentRow(i)
        self.refresh_marks()

    def toggle(self):
        if self.cur < 0:
            if self.paths:
                self.play_index(0)
        elif self.media.playbackState() == QMediaPlayer.PlayingState:
            self.media.pause()
        else:
            self.media.play()

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
        self.b_rep.setText("↻¹" if self.repeat == 2 else "↻")
        self.b_rep.setToolTip(["Repeat: off", "Repeat: all", "Repeat: one track"][self.repeat])

    # ---------- media signals ----------
    def on_pos(self, ms):
        self.t_cur.setText(fmt(ms))
        if not self.scrubbing:
            self.seek.setValue(ms)

    def on_dur(self, ms):
        self.seek.setRange(0, ms)
        self.t_tot.setText(fmt(ms))

    def on_state(self, st):
        self.b_play.setText("❚❚" if st == QMediaPlayer.PlayingState else "▶")

    def on_status(self, st):
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
        if title:
            self.title.setText(title)
        if artist:
            self.artist.setText(artist)
        img = md.value(K.CoverArtImage) or md.value(K.ThumbnailImage)
        if isinstance(img, QImage) and not img.isNull():
            self.set_cover(img)

    def set_cover(self, img):
        self.cover.setPixmap(make_cover(img))


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
    args = [os.path.abspath(a) for a in sys.argv[1:]]
    if send_to_running(args):  # already open: pass files over and exit
        sys.exit(0)
    icon = resource_path("icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    app.setFont(QFont("Segoe UI", 10))
    win = HazeAudio()
    win.show()
    if args:
        win.add_paths(args, force=True)
    sys.exit(app.exec())
