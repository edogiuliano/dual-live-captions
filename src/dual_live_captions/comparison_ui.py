"""Opt-in live comparison dashboard. Reports contain numbers, never transcripts."""
from collections import deque
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import statistics
import threading
import time
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QFormLayout
from .comparison import LiveComparison, percentile
from .comparison_windows import WindowCaptionReader, CaptionReadError


class ComparisonWorker(QThread):
    sample = Signal(dict)
    problem = Signal(str)

    def __init__(self):
        super().__init__()
        self.stop_requested = threading.Event()
        self.paused = threading.Event()
        self.language = "en"

    def run(self):
        import comtypes
        comtypes.CoInitialize()
        reader = None
        comparison = LiveComparison(self.language)
        last_sample = 0
        was_paused = False
        failed = False
        polling = deque(maxlen=600)
        read_times = deque(maxlen=600)
        previous_poll = None
        try:
            reader = WindowCaptionReader()
            while not self.stop_requested.is_set():
                started = time.perf_counter()
                if self.paused.is_set():
                    was_paused = True
                    self.stop_requested.wait(.1)
                    continue
                if self.language != comparison.language or was_paused:
                    comparison.language = self.language
                    comparison.reset()
                    reader.invalidate()
                    was_paused = False
                    previous_poll = None
                try:
                    windows_text, dual_texts, wt, dt, read_ms, rebound = reader.read()
                    if failed or (rebound and comparison.windows.current is not None):
                        comparison.reset()
                    failed = False
                    comparison.observe(windows_text, dual_texts, wt, dt)
                    # Text exists only in the bounded trackers and these locals.
                    windows_text, dual_texts = None, None
                    now = time.perf_counter()
                    if previous_poll is not None:
                        polling.append((now - previous_poll) * 1000)
                    previous_poll = now
                    read_times.append(read_ms)
                    if now - last_sample >= 1:
                        summary = comparison.summarize(now)
                        summary["poll_interval_median_ms"] = statistics.median(polling) if polling else None
                        summary["poll_interval_p95_ms"] = percentile(polling, .95)
                        summary["uia_read_median_ms"] = statistics.median(read_times)
                        summary["sample_clock"] = now
                        self.sample.emit(summary)
                        last_sample = now
                except Exception as exc:
                    message = str(exc) if isinstance(exc, CaptionReadError) else f"No se pudo leer el control de subtítulos ({type(exc).__name__})"
                    self.problem.emit(message)
                    reader.invalidate()
                    failed = True
                    previous_poll = None
                    self.stop_requested.wait(1)
                self.stop_requested.wait(max(0, .1 - (time.perf_counter() - started)))
        except Exception as exc:
            self.problem.emit(f"No se pudo iniciar la lectura de accesibilidad ({type(exc).__name__})")
        finally:
            reader = None
            comparison = None
            comtypes.CoUninitialize()


STYLE = """
QWidget {background:#141923;color:#e4eaf5;font-family:'Segoe UI';font-size:13px;}
QLabel#title {font-size:23px;font-weight:650;}
QLabel#value {font-size:30px;color:#a9d0ff;font-weight:650;}
QLabel#note {color:#98a8bf;font-size:12px;}
QLabel#status {color:#9ddbc0;}
QPushButton,QComboBox,QSpinBox {background:#26344a;border:1px solid #405675;border-radius:7px;padding:8px;}
QPushButton:hover {background:#344963;}
QPushButton:disabled {color:#687c96;}
"""


def new_report(language, minutes):
    return {
        "schema": 1,
        "algorithm_revision": 2,
        "started_at": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
        "type": "live UI accessibility comparison on existing Windows audio",
        "privacy": {"audio_recorded": False, "screenshots_saved": False, "transcripts_saved": False, "text_in_memory_only": True},
        "method": {
            "requested_duration_minutes": minutes,
            "comparison_panel": language,
            "windows_language_verified": False,
            "language_note": "Panel selected for comparison; Windows language is not changed by this tool.",
            "poll_target_ms": 100,
            "stability_ms": 1000,
            "rolling_retention_seconds": 180,
            "max_words_per_engine_in_alignment": 300,
            "minimum_context_words_for_timing": 3,
            "positive_delta_means": "Dual text was exposed after matching Windows text",
            "accuracy_reference": "none; Windows is not ground truth",
            "latency_reference": "first exact word exposed by UIA, including provisional text; not audio-to-display latency or camera-measured paint",
            "selection_bias": "timing includes only matching words in valid context; discrepant/missing words have no timing sample",
        },
        "status": "starting",
        "latest": None,
        "samples": [],
    }


class ComparisonWindow(QWidget):
    def __init__(self, report_path, minutes=30, language="en"):
        super().__init__()
        self.setWindowTitle("Comparación en vivo · Windows y Dual")
        self.resize(620, 650)
        self.setStyleSheet(STYLE)
        self.path = Path(report_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.report = new_report(language, minutes)
        self.samples = deque(maxlen=3600)
        self.epoch = time.perf_counter()
        self.last_save = -10
        self.completed = False
        self.limit_minutes = minutes
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(13)
        title = QLabel("Windows ↔ Dual Live Captions")
        title.setObjectName("title")
        layout.addWidget(title)
        self.status = QLabel("Conectando solo con las ventanas de subtítulos…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.lag = QLabel("—")
        self.lag.setObjectName("value")
        layout.addWidget(self.lag)
        self.lag_note = QLabel("Esperando palabras nuevas coincidentes")
        self.lag_note.setObjectName("note")
        layout.addWidget(self.lag_note)
        self.agreement = QLabel("Coincidencia de palabras: —")
        layout.addWidget(self.agreement)
        self.counts = QLabel("Muestra comparable: 0 palabras")
        layout.addWidget(self.counts)
        self.revisions = QLabel("Correcciones observadas: —")
        layout.addWidget(self.revisions)
        self.other_panel = QLabel("Panel de español: sin muestra nueva")
        self.other_panel.setObjectName("note")
        layout.addWidget(self.other_panel)
        self.timing = QLabel("Muestreo objetivo: 100 ms")
        self.timing.setObjectName("note")
        layout.addWidget(self.timing)
        form = QFormLayout()
        self.panel = QComboBox()
        self.panel.addItem("Inglés — usar si Windows está reconociendo inglés", "en")
        self.panel.addItem("Español — usar si Windows está reconociendo español", "es")
        self.panel.setCurrentIndex(0 if language == "en" else 1)
        form.addRow("Panel que se compara", self.panel)
        self.duration = QSpinBox()
        self.duration.setRange(1, 480)
        self.duration.setValue(minutes)
        self.duration.setSuffix(" min")
        form.addRow("Duración de la sesión", self.duration)
        layout.addLayout(form)
        note = QLabel("Coincidencia con Windows ≠ precisión real. Se comparan palabras estables entre anclas comunes, sin penalizar los extremos todavía retrasados. Las correcciones incluyen provisionales. +0,50 s significa que Dual apareció medio segundo después.\n\nVentana móvil: hasta 3 minutos / 300 palabras. No se guarda texto, audio ni capturas. No cambia idioma, privacidad, volumen ni la salida de Windows. Podés minimizar este comparador y seguir trabajando.")
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.pause_button = QPushButton("Pausar medición")
        self.finish_button = QPushButton("Terminar y guardar métricas")
        row.addWidget(self.pause_button)
        row.addWidget(self.finish_button)
        layout.addLayout(row)
        open_report = QPushButton("Abrir carpeta del informe")
        open_report.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path.parent))))
        layout.addWidget(open_report)
        self.worker = ComparisonWorker()
        self.worker.language = language
        self.worker.sample.connect(self.receive)
        self.worker.problem.connect(self.problem)
        self.panel.currentIndexChanged.connect(self.change_language)
        self.duration.valueChanged.connect(lambda value: setattr(self, "limit_minutes", value))
        self.pause_button.clicked.connect(self.pause)
        self.finish_button.clicked.connect(self.finish)
        self.worker.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.save()

    def change_language(self):
        self.worker.language = self.panel.currentData()
        self.report["method"]["comparison_panel"] = self.worker.language
        self.lag.setText("—")
        self.lag_note.setText("Se reinició la muestra para el panel seleccionado")

    def receive(self, sample):
        if self.completed:
            return
        elapsed = time.perf_counter() - self.epoch
        self.report["latest"] = sample
        self.report["status"] = "measuring"
        self.report.pop("read_problem", None)
        delta = sample["dual_minus_windows_median_ms"]
        if delta is None:
            self.lag.setText("—")
            self.lag_note.setText("Faltan frases nuevas coincidentes para calcular la diferencia")
        else:
            self.lag.setText(f"{delta / 1000:+.2f} s")
            p10 = sample["dual_minus_windows_p10_ms"] / 1000
            p90 = sample["dual_minus_windows_p90_ms"] / 1000
            direction = "Dual aparece después de Windows" if delta > 150 else "Dual aparece antes de Windows" if delta < -150 else "Aparecen aproximadamente a la vez"
            self.lag_note.setText(f"{direction}\nRango P10–P90: {p10:+.2f} a {p90:+.2f} s · mediana de palabras coincidentes")
        score = sample["word_agreement_percent"]
        self.agreement.setText(f"Coincidencia de palabras: {score:.1f}%" if score is not None else "Coincidencia de palabras: muestra insuficiente")
        self.counts.setText(f"Palabras comparadas: {sample['compared_words']} · con tiempo emparejado: {sample['matched_words']}")
        self.revisions.setText(f"Palabras provisionales corregidas: Windows {sample['windows_revised_words']} · Dual {sample['dual_revised_words']}")
        self.other_panel.setText(f"Palabras nuevas en Dual: inglés {sample['dual_en_observed_words']} · español {sample['dual_es_observed_words']}. El otro idioma queda fuera de esta comparación.")
        poll = sample["poll_interval_median_ms"]
        read = sample["uia_read_median_ms"]
        if poll is not None:
            self.timing.setText(f"Muestreo real: {poll:.0f} ms · lectura UIA: {read:.1f} ms · medida aproximada por accesibilidad")
        stale = sample["seconds_since_text_change"]
        self.status.setText(f"Midiendo · {elapsed / 60:.1f} / {self.limit_minutes} min" + (" · muestra pequeña" if sample["matched_words"] < 20 else "") + (f" · sin texto nuevo hace {stale:.0f} s" if stale is not None and stale > 5 else ""))
        if elapsed - self.last_save >= 2:
            self.samples.append({"elapsed_seconds": elapsed, **sample})
            self.last_save = elapsed
            self.save()

    def problem(self, message):
        if not self.completed:
            self.report["status"] = "waiting_for_caption_windows"
            self.report["read_problem"] = message
            self.status.setText(message)

    def pause(self):
        if self.worker.paused.is_set():
            self.worker.paused.clear()
            self.pause_button.setText("Pausar medición")
        else:
            self.worker.paused.set()
            self.pause_button.setText("Continuar medición")
            self.status.setText("Medición en pausa. Los subtítulos siguen funcionando.")
        self.report["status"] = "paused" if self.worker.paused.is_set() else "measuring"
        self.save()

    def tick(self):
        if not self.completed and time.perf_counter() - self.epoch >= self.limit_minutes * 60:
            self.finish()
        if self.completed and not self.worker.isRunning():
            self.timer.stop()

    def save(self):
        self.report["elapsed_seconds"] = time.perf_counter() - self.epoch
        self.report["samples"] = list(self.samples)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def finish(self):
        if self.completed:
            return
        self.completed = True
        self.worker.stop_requested.set()
        self.report["status"] = "finished"
        self.report["finished_at"] = datetime.now(timezone(timedelta(hours=-3))).isoformat()
        self.status.setText("Medición terminada. Windows y Dual siguen funcionando.")
        self.pause_button.setEnabled(False)
        self.finish_button.setEnabled(False)
        self.panel.setEnabled(False)
        self.save()

    def closeEvent(self, event):
        self.finish()
        if self.worker.isRunning():
            event.ignore()
            self.worker.finished.connect(self.close)
            return
        event.accept()


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Compare only caption windows; do not record audio/text")
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--report")
    parser.add_argument("--start-minimized", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    path = Path(args.report) if args.report else root / "artifacts/comparison" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S") / "report.json"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Comparación de subtítulos")
    window = ComparisonWindow(path, min(480, max(1, args.minutes)), args.language)
    if args.start_minimized:
        window.showMinimized()
    else:
        window.show()
    return app.exec()
