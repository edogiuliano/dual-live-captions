"""Real GUI + default WASAPI loopback + SAPI fixture playback. No user text saved."""
import json
from pathlib import Path
import sys
import time
import winsound
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from dual_live_captions.ui import MainWindow, STYLE
from dual_live_captions.settings import Settings, data_dir

ROOT = Path(__file__).resolve().parents[2]
(ROOT / "artifacts").mkdir(exist_ok=True)


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    settings_path = data_dir() / "settings.json"
    original = settings_path.read_bytes() if settings_path.exists() else None
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow(Settings(model="small"))
    window.history.enabled = True  # Synthetic test only; settings consent stays false.
    window.show()
    window.toggle_overlay()
    window.start()
    started = time.monotonic()
    report = {"kind": "real Windows WASAPI loopback and GUI, synthetic playback", "screens": [s.name() for s in app.screens()], "phases": []}
    played = False
    finished = False
    end = None
    phase = 0

    def tick():
        nonlocal played, end, finished, phase
        now = time.monotonic()
        if now - started > 100:
            report["timeout"] = True
            window.close()
            return
        if window.state == "running" and not played:
            fixture = ROOT / "artifacts/bilingual-fixture.wav"
            if not fixture.exists():
                report["error"] = "Run benchmark --stream first"
                window.close()
                return
            import wave
            with wave.open(str(fixture), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
            winsound.PlaySound(str(fixture), winsound.SND_FILENAME | winsound.SND_ASYNC)
            report["playback_seconds"] = duration
            report["phases"].append("default output playback started")
            end = now + duration + 3
            played = True
        if played and not finished and end and now >= end:
            items = window.history.ordered()
            report["confirmed_by_language"] = {lang: sum(c.language == lang for c in items) for lang in ("en", "es")}
            report["partials_visible"] = sum(bool(v) for p in window.panels.values() for v in p.partial.values())
            report["metrics"] = window.metrics
            report["engine"] = window.engine_device
            report["matching_english_reference"] = any("morning" in c.text.lower() for c in items if c.language == "en")
            report["matching_spanish_reference"] = any("turno" in c.text.lower() for c in items if c.language == "es")
            report["history_enabled_in_saved_settings"] = Settings.load().history_enabled
            window.grab().save(str(ROOT / "artifacts/main-window.png"))
            window.overlay.grab().save(str(ROOT / "artifacts/overlay.png"))
            # Move overlay to each real monitor and validate available geometry.
            report["overlay_screens"] = []
            for i, screen in enumerate(app.screens()):
                window.settings.overlay_screen = i
                window.overlay.place()
                app.processEvents()
                report["overlay_screens"].append({"name": screen.name(), "inside": screen.availableGeometry().contains(window.overlay.frameGeometry().center())})
            window.pause()
            report["phases"].append("pause:" + window.state)
            QTimer.singleShot(600, resume)
            finished = True

    def resume():
        window.pause()
        report["phases"].append("resume:" + window.state)
        window.through.setChecked(True)
        window.unlock()
        report["click_through_recovered"] = not window.overlay.click_through
        window.stop()
        report["phases"].append("stop requested")
        QTimer.singleShot(6500, conclude)

    def conclude():
        report["stopped"] = window.process is None
        (ROOT / "artifacts/windows-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        window.close()
        app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    app.exec()
    winsound.PlaySound(None, winsound.SND_PURGE)
    if original is not None:
        settings_path.write_bytes(original)
    else:
        settings_path.unlink(missing_ok=True)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
