"""Short, silent harness for mouse testing the real frameless overlay windows."""
import argparse
import json
from pathlib import Path
import sys
from collections import deque
from PySide6.QtCore import QTimer, QObject, QEvent
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from dual_live_captions.floating import OverlayManager
from dual_live_captions.settings import Settings
from dual_live_captions.subtitles import Caption
from dual_live_captions.ui import STYLE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--automation-host', action='store_true', help='Reference window for desktop tools that omit non-activating Tool windows')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    manager = OverlayManager(Settings())
    manager.persistence_enabled = False
    mouse_events = deque(maxlen=500)
    class Observer(QObject):
        def eventFilter(self, obj, event):
            if isinstance(obj, QWidget) and obj.window() in manager.windows.values():
                kind = event.type()
                if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.UngrabMouse) or (kind == QEvent.MouseMove and event.buttons()):
                    record = {'event':kind.name,'object':obj.objectName() or type(obj).__name__,'gesture':obj.window()._gesture is not None}
                    if hasattr(event, 'globalPosition'):
                        p=event.globalPosition().toPoint()
                        record.update({'global':[p.x(),p.y()],'buttons':event.buttons().value})
                    mouse_events.append(record)
            return False
    observer = Observer(app)
    app.installEventFilter(observer)
    host = None
    if args.automation_host:
        host = QWidget()
        host.setWindowTitle('Dual Live Captions · Prueba de mouse sin audio')
        layout = QVBoxLayout(host)
        layout.addWidget(QLabel('Prueba de movimiento y resize. Solo texto genérico; sin captura ni ASR.'))
        host.resize(1400, 850)
        host.move(100, 50)
        host.show()
        for window in manager.windows.values():
            window.setParent(host, window.windowFlags())
        manager.united.setGeometry(400, 300, 640, 300)
        manager.united.setProperty('placed', True)
        def arrange_split():
            if manager.settings.overlay_split:
                manager.windows['en'].setGeometry(160,150,640,260)
                manager.windows['es'].setGeometry(850,150,640,260)
        manager.united.split_requested.connect(arrange_split)
    for i in range(6):
        for lang, text in (('en', 'This is a silent window test. Move or resize the overlay to see more recent words.'), ('es', 'Esta es una prueba sin audio. Mové o redimensioná la ventana para ver más palabras recientes.')):
            manager.receive(Caption(str(i), 'test', lang, text, i * 3, i * 3 + 1, True))
    manager.show()
    manager.return_requested.connect(app.quit)
    events = []
    def record():
        snapshot = {k: [w.x(),w.y(),w.width(),w.height(),w.isVisible()] for k,w in manager.windows.items()}
        if not events or events[-1] != snapshot:
            events.append(snapshot)
        Path(args.output).write_text(json.dumps({'kind':'silent native mouse harness; no audio or ASR','automation_host':args.automation_host,'states':events,'mouse_events':list(mouse_events)},indent=2),encoding='utf-8')
    timer = QTimer()
    timer.timeout.connect(record)
    timer.start(100)
    QTimer.singleShot(args.seconds * 1000, app.quit)
    app.exec()
    record()
    manager.shutdown()


if __name__ == '__main__':
    main()
