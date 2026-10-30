from dataclasses import replace
from pathlib import Path
import json
import multiprocessing as mp
import queue
import threading
import time
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QIcon, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QProgressBar, QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QTabWidget, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QSystemTrayIcon, QMenu, QFrame, QSplitter, QToolButton, QWidgetAction)
from .settings import Settings, PROFILES, data_dir
from .models import MODELS, cached_model, download
from .audio import enumerate_devices
from .overlay import CaptionPanel
from .floating import OverlayManager
from .hotkeys import Hotkeys, parse_hotkey
from .subtitles import History
from .service import run_service

STYLE = """
QWidget { background:#11151d; color:#e8ecf4; font-family:'Segoe UI'; font-size:13px; }
QMainWindow, QDialog { background:#11151d; }
QLabel { background:transparent; }
QLabel#brand { font-size:16px; font-weight:700; letter-spacing:1px; }
QLabel#eyebrow { color:#7da9e7; font-size:10px; font-weight:600; letter-spacing:2px; }
QLabel#muted { color:#8c98ac; font-size:11px; }
QLabel#status { color:#94d4b4; background:#1a302a; border-radius:8px; padding:6px 10px; }
QLabel#panelTitle { color:#b8c6db; font-size:11px; font-weight:700; letter-spacing:2px; }
QLabel#languageTag { color:#9dc0f4; background:#27354b; border-radius:6px; font-size:10px; font-weight:700; }
QFrame#captionPanel { background:#1a202c; border:1px solid #2b3444; border-radius:14px; }
QFrame#captionPanel QLabel { border:0; }
QFrame#toolbar { background:#171e29; border-radius:10px; }
QPushButton { background:#252e3e; border:1px solid #354158; border-radius:7px; padding:9px 15px; font-weight:600; }
QPushButton:hover { background:#303e54; border-color:#6382b0; }
QPushButton:pressed { background:#1a2537; }
QPushButton:disabled { color:#626d80; background:#1a202c; border-color:#293140; }
QPushButton#primary { color:#101b2b; background:#a8cafa; border:0; }
QPushButton#primary:hover { background:#c0dcff; }
QPushButton#primary:disabled { background:#26384f; color:#7388a5; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background:#1c2533; border:1px solid #354158; border-radius:6px; padding:7px; min-height:20px; }
QComboBox QAbstractItemView { background:#202a3b; selection-background-color:#364c6d; }
QProgressBar { background:#273143; border:0; border-radius:3px; max-height:5px; }
QProgressBar::chunk { background:#8fb8ef; border-radius:3px; }
QTabWidget::pane { border:1px solid #303b4e; border-radius:8px; }
QTabBar::tab { padding:11px 18px; background:#1a2230; }
QTabBar::tab:selected { background:#2b3c55; color:#c2d9f8; }
QTextEdit { background:#171e29; border:1px solid #303b4e; border-radius:8px; padding:10px; }
QCheckBox { spacing:8px; padding:4px; }
QWidget#overlay { background:#111720; border:1px solid #48566e; border-radius:12px; }
QLabel#overlayHeader { color:#a1b1c9; font-size:10px; letter-spacing:2px; padding:3px; }
QToolTip { color:#e8ecf4; background:#29354a; border:1px solid #526986; }
QToolButton {background:#252e3e;border:1px solid #354158;border-radius:7px;padding:8px 12px;}
QSplitter::handle {background:#11151d;}
QSplitter::handle:hover {background:#405675;}
"""


def app_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#23354f"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 15, 15)
    painter.setBrush(QColor("#b4d3ff"))
    painter.drawRoundedRect(12, 17, 40, 10, 4, 4)
    painter.setBrush(QColor("#76d5bd"))
    painter.drawRoundedRect(12, 36, 29, 10, 4, 4)
    painter.end()
    return QIcon(pix)


class DeviceScanner(QThread):
    result = Signal(object, object)
    failure = Signal(str)
    def run(self):
        try:
            a, b = enumerate_devices()
            self.result.emit(a, b)
        except Exception as exc:
            self.failure.emit(f"No se pueden enumerar dispositivos ({type(exc).__name__})")


class ModelDownload(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failure = Signal(str)
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.cancelled = threading.Event()
    def run(self):
        try:
            result = download(self.name, lambda a, b: self.progress.emit(a // 1024, b // 1024), self.cancelled)
            self.done.emit(result or "")
        except Exception as exc:
            self.failure.emit(f"Descarga incompleta ({type(exc).__name__}). Podés reintentar.")


class SettingsDialog(QDialog):
    def __init__(self, settings, outputs, inputs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración · Dual Live Captions")
        self.resize(610, 620)
        self.original = settings
        self.widgets = {}
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)
        def page(title):
            widget = QWidget()
            form = QFormLayout(widget)
            form.setContentsMargins(20, 20, 20, 20)
            form.setSpacing(14)
            tabs.addTab(widget, title)
            return form
        def combo(form, name, label, items):
            w = QComboBox()
            for title, value in items:
                w.addItem(title, value)
            index = w.findData(getattr(settings, name))
            w.setCurrentIndex(max(0, index))
            form.addRow(label, w)
            self.widgets[name] = w
            return w
        def spin(form, name, label, low, high, floating=False):
            w = QDoubleSpinBox() if floating else QSpinBox()
            w.setRange(low, high)
            if floating:
                w.setSingleStep(.05)
                w.setDecimals(2)
            w.setValue(getattr(settings, name))
            form.addRow(label, w)
            self.widgets[name] = w
        def check(form, name, label):
            w = QCheckBox(label)
            w.setChecked(getattr(settings, name))
            form.addRow(w)
            self.widgets[name] = w
        audio = page("Motor y audio")
        profile = combo(audio, "profile", "Perfil", [(p, p) for p in PROFILES])
        model = combo(audio, "model", "Modelo multilingüe", [(f"{m}  ·  ~{s} MB", m) for m, (_, s) in MODELS.items()])
        combo(audio, "device", "Procesamiento", [("Automático", "auto"), ("GPU NVIDIA", "cuda"), ("CPU · INT8", "cpu")])
        combo(audio, "compute_type", "Precisión GPU", [("FP16", "float16"), ("INT8 + FP16", "int8_float16")])
        check(audio, "system_audio", "Capturar audio de Windows")
        combo(audio, "output", "Salida de Windows", [("Seguir salida predeterminada", "default")] + [(d["name"], d["id"]) for d in outputs])
        combo(audio, "microphone", "Micrófono", [("Desactivado", "none"), ("Predeterminado", "default")] + [(d["name"], d["id"]) for d in inputs])
        warning = QLabel("Sistema y micrófono se procesan por separado. Con altavoces, el micrófono puede captar la misma voz; se recomiendan auriculares.\nCaptura por aplicación: pendiente en esta versión.")
        warning.setWordWrap(True)
        warning.setObjectName("muted")
        audio.addRow(warning)
        spin(audio, "vad_threshold", "Umbral de voz", .1, .95, True)
        self.english = QCheckBox("Inglés")
        self.spanish = QCheckBox("Español")
        self.english.setChecked("en" in settings.languages)
        self.spanish.setChecked("es" in settings.languages)
        audio.addRow(self.english, self.spanish)
        profile.currentIndexChanged.connect(lambda: model.setCurrentIndex(model.findData(PROFILES[profile.currentData()]["model"])))
        overlay = page("Overlay")
        spin(overlay, "font_size", "Tamaño del texto", 14, 64)
        spin(overlay, "opacity", "Opacidad", .25, 1, True)
        spin(overlay, "overlay_lines", "Altura inicial (líneas)", 1, 32)
        spin(overlay, "overlay_width", "Anchura inicial (px)", 480, 2400)
        combo(overlay, "caption_layout", "Distribución de idiomas", [("Lado a lado · paneles grandes", "columns"), ("Uno debajo del otro", "rows")])
        spin(overlay, "caption_word_limit", "Palabras recientes por idioma", 100, 2000)
        combo(overlay, "overlay_position", "Ubicación inicial", [("Abajo", "bottom"), ("Arriba", "top")])
        combo(overlay, "overlay_screen", "Monitor inicial", [(f"{i + 1} · {s.name()}", i) for i, s in enumerate(QApplication.screens())])
        check(overlay, "overlay_locked", "Bloquear movimiento y tamaño")
        check(overlay, "overlay_english", "Mostrar panel de inglés")
        check(overlay, "overlay_spanish", "Mostrar panel de español")
        label = QLabel("Se puede mover arrastrando la barra superior. Click-through se activa desde la ventana principal y se desactiva con Ctrl+Alt+U o desde la bandeja.")
        label.setWordWrap(True)
        overlay.addRow(label)
        privacy = page("Privacidad y atajos")
        check(privacy, "history_enabled", "Conservar historial en memoria durante esta sesión")
        spin(privacy, "retention_minutes", "Retención (minutos)", 1, 480)
        check(privacy, "start_minimized", "Abrir minimizado en la bandeja")
        for name, label in (("hotkey_overlay", "Mostrar / ocultar overlay"), ("hotkey_pause", "Pausar / continuar")):
            w = QLineEdit(getattr(settings, name))
            self.widgets[name] = w
            privacy.addRow(label, w)
        privacy.addRow(QLabel("Recuperar interacción: Ctrl+Alt+U (fijo)."))
        note = QLabel("Procesamiento local. Sin grabación de audio, telemetría ni envío de conversaciones. Historial solo en RAM; guardar un archivo requiere Exportar. Las descargas de modelos sí usan Internet.")
        note.setWordWrap(True)
        privacy.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def validate_accept(self):
        try:
            sequences = [self.widgets[n].text() for n in ("hotkey_overlay", "hotkey_pause")] + ["Ctrl+Alt+U"]
            parsed = [parse_hotkey(s) for s in sequences]
            if len(set(parsed)) != len(parsed):
                raise ValueError("Los atajos deben ser distintos")
            if not self.english.isChecked() and not self.spanish.isChecked():
                raise ValueError("Habilitá al menos un idioma")
            if not self.widgets["system_audio"].isChecked() and self.widgets["microphone"].currentData() == "none":
                raise ValueError("Habilitá al menos una fuente de audio")
            if not self.widgets["overlay_english"].isChecked() and not self.widgets["overlay_spanish"].isChecked():
                raise ValueError("El overlay necesita al menos un panel visible")
        except ValueError as exc:
            QMessageBox.warning(self, "Revisar configuración", str(exc))
            return
        self.accept()

    def result_settings(self):
        value = replace(self.original)
        new_profile = self.widgets["profile"].currentData()
        value.apply_profile(new_profile)
        for name, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                selected = widget.currentData()
            elif isinstance(widget, QCheckBox):
                selected = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                selected = widget.text()
            else:
                selected = widget.value()
            setattr(value, name, selected)
        value.languages = tuple(lang for lang, check in (("en", self.english), ("es", self.spanish)) if check.isChecked())
        value.validate()
        return value


class MainWindow(QMainWindow):
    def __init__(self, settings=None, scan=True):
        super().__init__()
        self.settings = settings or Settings.load()
        self.setWindowTitle("Dual Live Captions")
        self.setWindowIcon(app_icon())
        area = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1280, area.width() - 40), min(980, area.height() - 48))
        self.setMinimumSize(760, 580)
        self.process = None
        self.downloader = None
        self.outputs, self.inputs = [], []
        self.scanner = None
        self.ctx = mp.get_context("spawn")
        self.state = "stopped"
        self.cpu_retry = False
        self.pending_close = False
        self.session_epoch = time.monotonic()
        self.metrics = {}
        self.history = History(self.settings.history_enabled, self.settings.retention_minutes)
        self.overlays = OverlayManager(self.settings, self)
        self.overlay = self.overlays.united
        self.overlays.return_requested.connect(self.reveal)
        self.overlays.visual_requested.connect(self.personalize_overlay)
        self.visual_dialog = None
        self.quitting = False
        center = QWidget()
        self.setCentralWidget(center)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        brand = QLabel("DUAL LIVE CAPTIONS")
        brand.setObjectName("brand")
        header.addWidget(brand)
        self.status_badge = QLabel("●  Preparado")
        self.status_badge.setObjectName("status")
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        source_row = QHBoxLayout(toolbar)
        source_row.setContentsMargins(6, 0, 6, 0)
        self.source_combo = QComboBox()
        self.source_combo.setMinimumContentsLength(14)
        self.source_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.source_combo.addItem("Audio de Windows · salida predeterminada", "default")
        self.source_combo.currentIndexChanged.connect(self.source_changed)
        source_row.addWidget(self.source_combo, 1)
        self.scan_button = QPushButton("↻")
        self.scan_button.setToolTip("Actualizar dispositivos")
        self.scan_button.clicked.connect(self.scan_devices)
        source_row.addWidget(self.scan_button)
        header.addWidget(toolbar, 1)
        header.addWidget(self.status_badge)
        layout.addLayout(header)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(3)
        self.level.setToolTip("Nivel del audio recibido")
        layout.addWidget(self.level)
        self.panels = {lang: CaptionPanel(lang) for lang in ("en", "es")}
        self.caption_splitter = QSplitter(Qt.Horizontal if self.settings.caption_layout == "columns" else Qt.Vertical)
        self.caption_splitter.setObjectName("captionSplitter")
        self.caption_splitter.setChildrenCollapsible(False)
        self.caption_splitter.setHandleWidth(8)
        for panel in self.panels.values():
            panel.configure(self.settings.font_size, self.settings.overlay_lines, self.settings.caption_word_limit)
            self.caption_splitter.addWidget(panel)
        layout.addWidget(self.caption_splitter, 1)
        self.details = QLabel("Local · sin grabación de audio · historial desactivado" if not self.history.enabled else "Local · historial en memoria activado")
        self.details.setObjectName("muted")
        self.details.setWordWrap(False)
        layout.addWidget(self.details)
        row = QHBoxLayout()
        self.start_button = QPushButton("▶  Iniciar")
        self.start_button.setObjectName("primary")
        self.pause_button = QPushButton("Ⅱ  Pausar")
        self.stop_button = QPushButton("■  Detener")
        self.start_button.clicked.connect(self.start)
        self.pause_button.clicked.connect(self.pause)
        self.stop_button.clicked.connect(self.stop)
        row.addWidget(self.start_button)
        row.addWidget(self.pause_button)
        row.addWidget(self.stop_button)
        row.addStretch()
        self.overlay_button = QPushButton("↗  Overlay")
        self.overlay_button.clicked.connect(self.toggle_overlay)
        row.addWidget(self.overlay_button)
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Lado a lado", "columns")
        self.layout_combo.addItem("Apilados", "rows")
        self.layout_combo.setCurrentIndex(self.layout_combo.findData(self.settings.caption_layout))
        self.layout_combo.currentIndexChanged.connect(self.change_caption_layout)
        row.addWidget(self.layout_combo)
        self.expand_button = QPushButton("⛶ Ampliar")
        self.expand_button.setToolTip("Aprovechar toda la pantalla para leer párrafos")
        self.expand_button.clicked.connect(lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        row.addWidget(self.expand_button)
        self.more_menu = QMenu(self)
        for label, action in (("Configuración", self.configure), ("Personalización del overlay", self.personalize_overlay), ("Historial", self.show_history), ("Diagnóstico", self.diagnostics)):
            self.more_menu.addAction(label, action)
        self.through = QCheckBox("Click-through")
        self.through.setToolTip("Desactivar con Ctrl+Alt+U o desde la bandeja")
        self.through.toggled.connect(self.set_through)
        through_action = QWidgetAction(self.more_menu)
        through_action.setDefaultWidget(self.through)
        self.more_menu.addAction(through_action)
        self.more_button = QToolButton()
        self.more_button.setText("Más")
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        self.more_button.setMenu(self.more_menu)
        row.addWidget(self.more_button)
        layout.addLayout(row)
        self.download_bar = QProgressBar()
        self.download_bar.setMaximumHeight(14)
        self.download_bar.hide()
        layout.addWidget(self.download_bar)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        for label, action in (("Mostrar ventana", self.reveal), ("Mostrar / ocultar overlay", self.toggle_overlay), ("Recuperar interacción del overlay", self.unlock), ("Pausar / continuar", self.pause), ("Salir", self.exit_application)):
            menu.addAction(label, action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()
        self.register_hotkeys()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(40)
        self.device_timer = QTimer(self)
        self.device_timer.timeout.connect(self.scan_devices)
        self.device_timer.start(10000)
        self.set_state("stopped")
        if scan:
            self.scan_devices()

    def register_hotkeys(self):
        if hasattr(self, "hotkeys"):
            QApplication.instance().removeNativeEventFilter(self.hotkeys)
            self.hotkeys.close()
        self.hotkeys = Hotkeys(self, [(self.settings.hotkey_overlay, self.toggle_overlay), (self.settings.hotkey_pause, self.pause), ("Ctrl+Alt+U", self.unlock)])
        QApplication.instance().installNativeEventFilter(self.hotkeys)
        self.through.setEnabled(not any(e.startswith("Ctrl+Alt+U:") for e in self.hotkeys.errors))

    def reveal(self):
        self.overlays.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def set_state(self, state):
        self.state = state
        self.start_button.setEnabled(state == "stopped" and not self.downloader)
        self.pause_button.setEnabled(state in ("running", "paused"))
        self.stop_button.setEnabled(state in ("loading", "running", "paused"))
        self.source_combo.setEnabled(state == "stopped")
        self.pause_button.setText("▶  Continuar" if state == "paused" else "Ⅱ  Pausar")

    def source_changed(self):
        if self.state == "stopped":
            self.settings.output = self.source_combo.currentData() or "default"

    def change_caption_layout(self):
        self.settings.caption_layout = self.layout_combo.currentData()
        self.caption_splitter.setOrientation(Qt.Horizontal if self.settings.caption_layout == "columns" else Qt.Vertical)
        self.overlay.settings = self.settings
        self.overlay.apply_settings()
        self.overlay.place()
        self.settings.save()

    def scan_devices(self):
        if self.scanner and self.scanner.isRunning():
            return
        self.scanner = DeviceScanner()
        self.scanner.result.connect(self.devices_ready)
        self.scanner.failure.connect(lambda msg: self.details.setText(msg))
        self.scanner.start()

    def devices_ready(self, outputs, inputs):
        self.outputs, self.inputs = outputs, inputs
        selected = self.settings.output
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem("Audio de Windows · salida predeterminada", "default")
        for device in outputs:
            self.source_combo.addItem(device["name"], device["id"])
        index = self.source_combo.findData(selected)
        if index < 0:
            self.source_combo.addItem("Desconectado · " + selected, selected)
            index = self.source_combo.count() - 1
        self.source_combo.setCurrentIndex(index)
        self.source_combo.blockSignals(False)

    def start(self, force_cpu=False):
        if self.process is not None or self.downloader:
            return
        path = cached_model(self.settings.model)
        if not path:
            size = MODELS.get(self.settings.model, (None, 0))[1]
            answer = QMessageBox.question(self, "Preparar modelo local", f"Se descargará {self.settings.model} (~{size} MB) desde Hugging Face. La descarga solo contiene el modelo; tus conversaciones permanecen en esta computadora.\n\n¿Descargar y verificar ahora?")
            if answer != QMessageBox.Yes:
                return
            self.downloader = ModelDownload(self.settings.model)
            self.downloader.progress.connect(self.download_progress)
            self.downloader.done.connect(self.download_done)
            self.downloader.failure.connect(self.download_failed)
            self.download_bar.show()
            self.status_badge.setText("●  Descargando modelo")
            self.downloader.start()
            self.set_state("stopped")
            return
        self.settings.save()
        self.cpu_retry = force_cpu
        self.events = self.ctx.Queue(maxsize=256)
        self.stop_event, self.paused_event = self.ctx.Event(), self.ctx.Event()
        settings = replace(self.settings, device="cpu") if force_cpu else self.settings
        self.process = self.ctx.Process(target=run_service, args=(settings, path, self.events, self.stop_event, self.paused_event, self.session_epoch), name="DualCaptions-ASR", daemon=True)
        self.process.start()
        self.set_state("loading")
        self.status_badge.setText("●  Cargando modelo")
        self.details.setText("Preparando reconocimiento local…")
        self.stop_deadline = None
        self.engine_device = None
        self.loading_deadline = time.monotonic() + 90
        self.inference_deadline = None

    def download_progress(self, current, total):
        self.download_bar.setRange(0, max(1, total))
        self.download_bar.setValue(current)
        self.details.setText(f"Modelo: {current / 1024:.1f} / {total / 1024:.1f} MB · descarga verificada al terminar")

    def download_done(self, path):
        self.downloader.wait(1000)
        self.downloader = None
        self.download_bar.hide()
        self.set_state("stopped")
        if path:
            self.start()

    def download_failed(self, message):
        self.downloader.wait(1000)
        self.downloader = None
        self.download_bar.hide()
        self.set_state("stopped")
        self.status_badge.setText("●  Descarga incompleta")
        self.details.setText(message)

    def pause(self):
        if self.state == "running":
            self.paused_event.set()
            self.set_state("paused")
            self.status_badge.setText("●  En pausa")
        elif self.state == "paused":
            self.paused_event.clear()
            self.set_state("running")
            self.status_badge.setText("●  Capturando")

    def stop(self):
        if self.process:
            self.stop_event.set()
            self.stop_deadline = time.monotonic() + 5
            self.set_state("stopping")
            self.status_badge.setText("●  Deteniendo")

    def poll(self):
        if not self.process:
            return
        for _ in range(180):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "caption":
                # Drain pre-pause events without showing new speech while paused.
                if self.state not in ("paused", "stopping") or not value.text:
                    self.panels[value.language].receive(value)
                    self.overlays.receive(value)
                    self.history.add(value)
                    self.metrics["ui_delivery_ms"] = max(0, (time.monotonic() - value.published) * 1000)
            elif kind == "engine":
                self.engine_device = value
                self.loading_deadline = None
            elif kind == "busy":
                self.inference_deadline = time.monotonic() + 30 if value else None
            elif kind == "status":
                self.details.setText(value)
                if value == "Capturando" and self.state != "stopping":
                    self.set_state("running")
                    self.status_badge.setText("●  Capturando")
            elif kind == "level":
                self.level.setValue(round(value * 100) if self.state == "running" else 0)
            elif kind == "metrics":
                self.metrics.update(value)
                self.details.setText(f"{(self.engine_device or 'CPU').upper()} · {self.settings.model} · inferencia {value['inference_ms']:.0f} ms · publicación {value['capture_to_publish_ms']:.0f} ms · historial {'en RAM' if self.history.enabled else 'desactivado'}")
            elif kind == "error":
                self.details.setText(value)
                self.status_badge.setText("●  Error recuperable")
            elif kind == "dropped":
                self.metrics["dropped_frames"] = value
        watchdog = (self.loading_deadline and time.monotonic() > self.loading_deadline) or (self.inference_deadline and time.monotonic() > self.inference_deadline)
        if watchdog and self.process.is_alive() and self.state != "stopping":
            self.details.setText("El motor no responde. Recuperando el proceso…")
            self.process.terminate()
        if self.stop_deadline and time.monotonic() >= self.stop_deadline and self.process.is_alive():
            self.process.terminate()
        if not self.process.is_alive():
            code = self.process.exitcode
            was_stopping = self.state == "stopping"
            self.process.join(timeout=.2)
            self.process.close()
            self.process = None
            self.events.close()
            self.events.cancel_join_thread()
            self.set_state("stopped")
            self.level.setValue(0)
            for panel in list(self.panels.values()) + list(self.overlays.panels.values()):
                panel.partial.clear()
                panel.render()
            if code and not was_stopping and not self.cpu_retry and self.settings.device != "cpu":
                self.details.setText("El proceso GPU terminó; reiniciando en CPU")
                self.start(force_cpu=True)
            else:
                self.status_badge.setText("●  Detenido" if not code or was_stopping else "●  Error del motor")
            if self.pending_close:
                self.close()

    def toggle_overlay(self):
        if self.overlays.isVisible():
            self.reveal()
        else:
            if not self.settings.overlay_english and not self.settings.overlay_spanish:
                self.settings.overlay_english = self.settings.overlay_spanish = True
                self.overlays.apply_settings()
            self.overlays.show()
            self.hide()

    def set_through(self, value):
        if value and not self.through.isEnabled():
            self.through.setChecked(False)
            return
        self.overlays.set_click_through(value)

    def unlock(self):
        self.through.setChecked(False)
        self.overlays.set_click_through(False)

    def personalize_overlay(self, language="united"):
        from .personalization import PersonalizationDialog
        if self.visual_dialog is None:
            self.visual_dialog = PersonalizationDialog(self.settings, language, self)
            self.visual_dialog.changed.connect(self._overlay_visual_changed)
            self.visual_dialog.finished.connect(lambda _: self.overlays.save())
        else:
            self.visual_dialog.settings = self.settings
            if language in ("en", "es"):
                self.visual_dialog.language.setCurrentIndex(1 if language == "es" else 0)
            self.visual_dialog.load_style()
        self.visual_dialog.show()
        self.visual_dialog.raise_()
        self.visual_dialog.activateWindow()

    def _overlay_visual_changed(self):
        self.overlays.apply_settings()
        self.overlays._saving.start(300)

    def exit_application(self):
        self.quitting = True
        self.close()

    def configure(self):
        dialog = SettingsDialog(self.settings, self.outputs, self.inputs, self)
        if dialog.exec() == QDialog.Accepted:
            previous = self.settings
            self.settings = dialog.result_settings()
            # Keep the existing global font/height/opacity controls useful.
            from .overlay_style import style_for
            if any(getattr(previous, key) != getattr(self.settings, key) for key in ("font_size", "opacity", "overlay_lines")):
                for lang in ("en", "es"):
                    self.settings.overlay_styles.setdefault(lang, style_for(previous, lang).to_dict())
            for style in self.settings.overlay_styles.values():
                for old_key, style_key in (("font_size", "font_size"), ("opacity", "background_opacity"), ("overlay_lines", "max_lines")):
                    if getattr(previous, old_key) != getattr(self.settings, old_key):
                        style[style_key] = getattr(self.settings, old_key)
            self.settings.save()
            self.history.enabled = self.settings.history_enabled
            self.history.retention_minutes = self.settings.retention_minutes
            if not self.history.enabled:
                self.history.clear()
            self.overlays.settings = self.settings
            reset_geometry = any(getattr(previous, key) != getattr(self.settings, key) for key in ("overlay_width", "overlay_screen", "overlay_position"))
            self.overlays.apply_settings(reset_geometry=reset_geometry)
            if self.visual_dialog:
                self.visual_dialog.settings = self.settings
            for panel in self.panels.values():
                panel.configure(self.settings.font_size, self.settings.overlay_lines, self.settings.caption_word_limit)
            self.caption_splitter.setOrientation(Qt.Horizontal if self.settings.caption_layout == "columns" else Qt.Vertical)
            self.layout_combo.blockSignals(True)
            self.layout_combo.setCurrentIndex(self.layout_combo.findData(self.settings.caption_layout))
            self.layout_combo.blockSignals(False)
            self.register_hotkeys()
            self.devices_ready(self.outputs, self.inputs)
            self.details.setText("Configuración guardada. Cambios del motor y audio: Detener → Iniciar.")

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Historial local · solo memoria")
        dialog.resize(760, 540)
        layout = QVBoxLayout(dialog)
        label = QLabel("Historial activado en memoria" if self.history.enabled else "Historial desactivado. Se habilita en Configuración → Privacidad.")
        layout.addWidget(label)
        text = QTextEdit()
        text.setReadOnly(True)
        from .subtitles import srt_time
        text.setPlainText("\n".join(f"[{srt_time(c.start)}] {c.language.upper()} · {c.source}: {c.text}" for c in self.history.ordered()))
        layout.addWidget(text)
        row = QHBoxLayout()
        copy = QPushButton("Copiar todo")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(text.toPlainText()))
        row.addWidget(copy)
        export = QPushButton("Exportar TXT / SRT / JSON")
        export.clicked.connect(self.export_history)
        row.addWidget(export)
        clear = QPushButton("Limpiar")
        clear.clicked.connect(lambda: (self.history.clear(), text.clear()))
        row.addWidget(clear)
        layout.addLayout(row)
        dialog.exec()

    def export_history(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar historial", "captions.txt", "Texto (*.txt);;SubRip (*.srt);;JSON (*.json)")
        if path:
            try:
                self.history.export(path)
            except OSError:
                QMessageBox.warning(self, "Exportación", "No se pudo escribir el archivo seleccionado.")

    def diagnostics(self):
        from .diagnostics import report
        dialog = QDialog(self)
        dialog.setWindowTitle("Diagnóstico · sin conversaciones")
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        info = report()
        info["session_metrics"] = self.metrics
        info["hotkey_errors"] = self.hotkeys.errors
        text.setPlainText(json.dumps(info, ensure_ascii=False, indent=2))
        layout.addWidget(text)
        button = QPushButton("Copiar diagnóstico")
        button.clicked.connect(lambda: QApplication.clipboard().setText(text.toPlainText()))
        layout.addWidget(button)
        gpu = QPushButton("Seleccionar carpeta de bibliotecas CUDA / cuDNN")
        def select_gpu():
            folder = QFileDialog.getExistingDirectory(dialog, "Carpeta con cuBLAS CUDA 12 y cuDNN 9")
            if not folder:
                return
            if not all((Path(folder) / name).is_file() for name in ("cublas64_12.dll", "cudnn64_9.dll")):
                QMessageBox.warning(dialog, "Bibliotecas GPU", "La carpeta debe contener cublas64_12.dll y cudnn64_9.dll, junto con sus dependencias.")
                return
            (data_dir() / "gpu-paths.json").write_text(json.dumps([folder]), encoding="utf-8")
            QMessageBox.information(dialog, "Bibliotecas GPU", "Ruta guardada. Detené e iniciá el reconocimiento para usarla.")
        gpu.clicked.connect(select_gpu)
        layout.addWidget(gpu)
        dialog.exec()

    def closeEvent(self, event):
        if self.process:
            self.pending_close = True
            self.stop()
            event.ignore()
            return
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancelled.set()
            self.pending_close = True
            self.downloader.finished.connect(self.close)
            event.ignore()
            return
        if self.scanner and self.scanner.isRunning():
            self.scanner.wait(3000)
            if self.scanner.isRunning():
                event.ignore()
                QTimer.singleShot(500, self.close)
                return
        self.timer.stop()
        self.device_timer.stop()
        self.hotkeys.close()
        QApplication.instance().removeNativeEventFilter(self.hotkeys)
        if self.visual_dialog:
            self.visual_dialog.close()
        self.overlays.shutdown()
        self.tray.hide()
        self.history.clear()
        event.accept()
        if self.quitting:
            QTimer.singleShot(0, QApplication.instance().quit)
