import multiprocessing
import os
import sys


def main():
    multiprocessing.freeze_support()
    # Disable network metadata checks during normal local inference.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from PySide6.QtGui import QFont
    from .runtime import setup_logging
    from .ui import MainWindow, STYLE
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Dual Live Captions")
    app.setOrganizationName("DualLiveCaptions")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    if "--ui-check" in sys.argv:
        from .settings import Settings
        window = MainWindow(Settings())
        window.overlays.persistence_enabled = False
    else:
        window = MainWindow()
    if "--ui-check" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--ui-check", required=True)
        options = parser.parse_args()
        from .ui_check import install
        window.show()
        window.ui_check_timer = install(app, window, options.ui_check)
        return app.exec()
    if "--self-test" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-test", required=True)
        parser.add_argument("--audio", required=True)
        options = parser.parse_args()
        from .selftest import install
        window.show()
        window.self_test_timer = install(app, window, options.self_test, options.audio)
        return app.exec()
    if window.settings.start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
