"""Dispatch actual QWidget mouse events, rather than just checking edge flags."""
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QSize, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from dual_live_captions.floating import OverlayManager, pointer_geometry
from dual_live_captions.settings import Settings
from dual_live_captions.subtitles import Caption
from dual_live_captions.ui import STYLE


def mouse(target, kind, global_pos):
    button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
    buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
    event = QMouseEvent(kind, QPointF(target.mapFromGlobal(global_pos)), QPointF(global_pos), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(target, event)


def drag(window, target, start, delta):
    origin = target.mapToGlobal(start)
    mouse(target, QEvent.MouseButtonPress, origin)
    assert window._gesture is not None
    mouse(window, QEvent.MouseMove, origin + delta)
    mouse(window, QEvent.MouseButtonRelease, origin + delta)
    assert window._gesture is None
    assert QWidget.mouseGrabber() is not window


@pytest.fixture(params=["united", "united_rows", "en", "es"])
def host(request, qtbot, qapp):
    qapp.setStyleSheet(STYLE)
    manager = OverlayManager(Settings(overlay_split=not request.param.startswith("united"), caption_layout="rows" if request.param == "united_rows" else "columns"))
    for w in manager.windows.values():
        qtbot.addWidget(w)
    manager.show()
    window = manager.windows["united" if request.param == "united_rows" else request.param]
    window.setGeometry(500, 400, 640, 260)
    qapp.processEvents()
    yield manager, window
    manager.shutdown()


@pytest.mark.parametrize("name,point,delta,expected", [
    ("top", (320,2), (0,-170), (500,230,640,430)),
    ("bottom", (320,258), (0,170), (500,400,640,430)),
    ("left", (2,130), (-170,0), (330,400,810,260)),
    ("right", (638,130), (170,0), (500,400,810,260)),
    ("top_left", (2,2), (-170,-170), (330,230,810,430)),
    ("top_right", (638,2), (170,-170), (500,230,810,430)),
    ("bottom_left", (2,258), (-170,170), (330,400,810,430)),
    ("bottom_right", (638,258), (170,170), (500,400,810,430)),
])
def test_mouse_resizes_every_edge_and_corner_and_keeps_opposite_anchor(host, name, point, delta, expected):
    manager, w = host
    others = {key: value.geometry() for key,value in manager.windows.items() if value is not w}
    drag(w, w, QPoint(*point), QPoint(*delta))
    assert w.geometry() == QRect(*expected), name
    assert all(manager.windows[key].geometry() == rect for key,rect in others.items())


def test_drag_from_header_and_empty_caption_surface_keeps_positions_after_idle(host, qtbot):
    manager, w = host
    panel = next(iter(w.panels.values()))
    drag(w, panel.tag, panel.tag.rect().center(), QPoint(-500,-400))
    assert w.pos() == QPoint(0,0)
    qtbot.wait(450)
    assert w.pos() == QPoint(0,0)
    text = panel.text
    # Empty area below the waiting caption, inside the scrollable QLabel.
    drag(w, text, QPoint(80,160), QPoint(200,150))
    assert w.pos() == QPoint(200,150)


def test_timer_does_not_snap_a_held_drag_to_a_monitor(host, qtbot):
    _, w = host
    panel = next(iter(w.panels.values()))
    origin = panel.tag.mapToGlobal(panel.tag.rect().center())
    mouse(panel.tag, QEvent.MouseButtonPress, origin)
    mouse(w, QEvent.MouseMove, origin + QPoint(-1600,-800))
    chosen = QRect(w.geometry())
    assert chosen.topLeft() == QPoint(-1100,-400)
    qtbot.wait(500)
    assert w.geometry() == chosen
    assert w._gesture is not None
    mouse(w, QEvent.MouseButtonRelease, origin + QPoint(-1600,-800))
    qtbot.wait(450)
    assert w.geometry() == chosen


def test_scrolled_off_text_cannot_intercept_the_header(host, qtbot):
    manager, w = host
    for lang in w.panels:
        manager.receive(Caption("full", "system", lang, " ".join("word"+str(i) for i in range(500)), 0, 1, True))
    qtbot.waitUntil(lambda: all(not p._updating_view for p in w.panels.values()))
    before = QRect(w.geometry())
    # Blank header between language badge and state, above a scrolled document.
    panel = next(iter(w.panels.values()))
    global_pos = panel.tag.mapToGlobal(panel.tag.rect().center() + QPoint(65,0))
    target = w.childAt(w.mapFromGlobal(global_pos))
    mouse(target, QEvent.MouseButtonPress, global_pos)
    assert w._gesture is not None
    mouse(w, QEvent.MouseMove, global_pos + QPoint(-120,-80))
    mouse(w, QEvent.MouseButtonRelease, global_pos + QPoint(-120,-80))
    assert w.geometry() == before.translated(-120,-80)


def test_buttons_and_selectable_caption_text_do_not_start_drag(host):
    _, w = host
    before = QRect(w.geometry())
    w.toolbar.show()
    hits = []
    w.visual_requested.connect(hits.append)
    button = w.visual_button
    position = button.mapToGlobal(button.rect().center())
    mouse(button, QEvent.MouseButtonPress, position)
    assert w._gesture is None
    mouse(button, QEvent.MouseButtonRelease, position)
    assert hits == [w.key]
    panel = next(iter(w.panels.values()))
    position = panel.text.mapToGlobal(QPoint(5,5))
    mouse(panel.text, QEvent.MouseButtonPress, position)
    assert w._gesture is None
    mouse(panel.text, QEvent.MouseButtonRelease, position)
    assert w.geometry() == before


def test_growing_to_monitor_height_shows_more_history_without_changing_font(host, qtbot, qapp):
    manager, w = host
    lang, panel = next(iter(w.panels.items()))
    text = " ".join("word"+str(i) for i in range(480))
    manager.receive(Caption("history", "system", lang, text, 0, 1, True))
    qtbot.waitUntil(lambda: not panel._updating_view)
    font_size = panel.text.font().pixelSize()
    before = panel.scroll.viewport().height()
    w.resize(1000, 850)
    qtbot.waitUntil(lambda: panel.scroll.viewport().height() > before + (200 if manager.settings.caption_layout == "rows" else 400))
    assert panel.text.font().pixelSize() == font_size
    assert panel._document.toPlainText() == text
    assert w.maximumHeight() >= max(s.availableGeometry().height() for s in qapp.screens())
    w.resize(500,120)
    qtbot.waitUntil(lambda: not panel._updating_view)
    bar = panel.scroll.verticalScrollBar()
    assert bar.value() == bar.maximum()
    assert panel._document.toPlainText() == text


def test_resize_minimum_and_maximum_keep_opposite_edges_fixed():
    rect = QRect(500,400,640,260)
    minimum, maximum = QSize(280,92), QSize(1920,1040)
    tiny = pointer_geometry(rect,QPoint(5000,5000),Qt.LeftEdge|Qt.TopEdge,minimum,maximum)
    huge = pointer_geometry(rect,QPoint(-5000,-5000),Qt.LeftEdge|Qt.TopEdge,minimum,maximum)
    assert tiny.size() == minimum and huge.size() == maximum
    assert tiny.right() == huge.right() == rect.right()
    assert tiny.bottom() == huge.bottom() == rect.bottom()
