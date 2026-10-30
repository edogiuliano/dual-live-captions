"""Explicit release verification mode; never enabled during normal app use."""
import json
from pathlib import Path
import time
import winsound
from PySide6.QtCore import QTimer
from . import __version__


def install(app, window, output, audio):
    output = Path(output)
    audio = Path(audio)
    report = {"version": __version__, "packaged": True, "audio": "explicit synthetic test fixture", "phases": [], "partial_en": 0, "partial_es": 0}
    epoch = time.monotonic()
    state = {"played": False, "end": None, "closing": False, "seen_partials": set()}
    # No history setting is enabled or saved; a bounded in-memory counter is enough.
    window.toggle_overlay()
    window.start()
    timer = QTimer(window)

    def conclude():
        report["stopped"] = window.process is None
        report["seconds"] = time.monotonic() - epoch
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        window.close()
        app.quit()

    def tick():
        now = time.monotonic()
        if now - epoch > 95 and not state["closing"]:
            report["timeout"] = True
            window.stop()
            state["closing"] = True
            QTimer.singleShot(6000, conclude)
        if window.state == "running" and not state["played"]:
            import wave
            with wave.open(str(audio), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
            winsound.PlaySound(str(audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
            state["end"] = now + duration + 2
            state["played"] = True
            report["phases"].append("WASAPI playback started")
        for language, panel in window.panels.items():
            for text in panel.partial.values():
                key = (language, text)
                if text and key not in state["seen_partials"]:
                    state["seen_partials"].add(key)
                    report[f"partial_{language}"] += 1
        if state["end"] and now >= state["end"] and not state["closing"]:
            report["confirmed_panels"] = {lang: bool(panel.confirmed) for lang, panel in window.panels.items()}
            report["engine"] = window.engine_device
            report["metrics"] = window.metrics
            window.grab().save(str(output.with_suffix(".png")))
            window.pause()
            report["phases"].append(window.state)
            window.pause()
            report["phases"].append(window.state)
            window.stop()
            state["closing"] = True
            QTimer.singleShot(6000, conclude)
    timer.timeout.connect(tick)
    timer.start(50)
    return timer
