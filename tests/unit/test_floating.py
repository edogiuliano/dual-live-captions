import json
import ctypes
import sys
from dataclasses import replace
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDialog
from dual_live_captions.floating import OverlayManager, bounded_geometry
from dual_live_captions.overlay_style import OverlayStyle, style_for
from dual_live_captions.settings import Settings
from dual_live_captions.subtitles import Caption
from dual_live_captions.ui import MainWindow, STYLE


def caption(lang="en", text="Hello from the live audio", number=0, final=True):
    return Caption(str(number), "system", lang, text, number * 3, number * 3 + 1, final)


def manager(qtbot, qapp):
    qapp.setStyleSheet(STYLE)
    value = OverlayManager(Settings())
    for window in value.windows.values():
        qtbot.addWidget(window)
    return value


def test_overlay_hides_main_and_return_keeps_engine_identity(qtbot):
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    window.show()
    sentinel = object()
    window.process = sentinel
    window.toggle_overlay()
    assert not window.isVisible()
    assert window.overlays.united.isVisible()
    assert window.process is sentinel
    window.overlays.receive(caption())
    assert "Hello" in window.overlays.panels["en"].text.text()
    window.overlays.united.return_button.click()
    assert window.isVisible() and not window.overlays.isVisible()
    assert window.process is sentinel
    window.process = None
    window.close()


def test_split_reparents_same_panels_and_never_duplicates_captions(qtbot, qapp):
    value = manager(qtbot, qapp)
    original = dict(value.panels)
    value.receive(caption())
    value.receive(caption("es", "Buen día, seguimos escuchando"))
    before = {k: p.text.text() for k, p in value.panels.items()}
    value.show()
    for _ in range(3):
        value.toggle_split()
        assert not value.united.isVisible()
        assert value.windows["en"].isVisible() and value.windows["es"].isVisible()
        assert value.panels == original
        assert value.panels["en"].window() is value.windows["en"]
        assert value.panels["es"].window() is value.windows["es"]
        value.toggle_split()
        assert value.united.isVisible()
        assert not value.windows["en"].isVisible()
        assert {k: p.text.text() for k, p in value.panels.items()} == before
    value.shutdown()


def test_separate_geometry_visibility_and_hidden_updates_are_independent(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.show()
    value.toggle_split()
    en, es = value.windows["en"], value.windows["es"]
    es_before = es.geometry()
    en.move(40, 50)
    en.resize(700, 210)
    assert es.geometry() == es_before
    value.hide_window("en")
    assert es.isVisible() and not en.isVisible()
    value.receive(caption("en", "Still captured while this language is hidden"))
    assert "Still captured" in value.panels["en"].text.text()
    value.shutdown()


def test_resize_preserves_history_wrap_and_follow_latest(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.show()
    value.toggle_split()
    panel, window = value.panels["en"], value.windows["en"]
    text = " ".join("word" + str(i) for i in range(470))
    value.receive(caption(text=text))
    qtbot.waitUntil(lambda: not panel._updating_view)
    window.resize(350, 140)
    qtbot.waitUntil(lambda: panel.scroll.viewport().width() < 350)
    small_height = panel._document.size().height()
    window.resize(800, 250)
    qtbot.waitUntil(lambda: panel.scroll.viewport().width() > 700 and not panel._updating_view)
    assert panel._document.size().height() < small_height
    assert panel._document.toPlainText() == text
    bar = panel.scroll.verticalScrollBar()
    assert bar.value() == bar.maximum()
    bar.setValue(bar.maximum() // 2)
    value.receive(caption(text="more live words", number=2))
    qtbot.waitUntil(lambda: not panel._updating_view)
    assert not panel.follow_latest
    panel.jump_to_latest()
    qtbot.waitUntil(lambda: not panel._updating_view)
    assert bar.value() == bar.maximum()
    value.shutdown()


def test_long_unbroken_word_does_not_expand_or_clip_viewport(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.show()
    value.toggle_split()
    w, panel = value.windows["en"], value.panels["en"]
    w.resize(340, 200)
    value.receive(caption(text="https://example.com/" + "a" * 250))
    qtbot.waitUntil(lambda: not panel._updating_view)
    assert panel.text.width() <= panel.scroll.viewport().width()
    assert panel._document.idealWidth() <= panel.scroll.viewport().width() + 1
    value.shutdown()


def test_hover_tools_do_not_take_caption_space(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.show()
    window = value.united
    window.toolbar.hide()
    before = value.panels["en"].scroll.viewport().size()
    QApplication.sendEvent(window, QEnterEvent(QPoint(20, 20), QPoint(20, 20), window.mapToGlobal(QPoint(20, 20))))
    assert window.toolbar.isVisible()
    assert value.panels["en"].scroll.viewport().size() == before
    window.toolbar.hide()
    assert value.panels["en"].scroll.viewport().size() == before
    value.shutdown()


def test_all_four_edges_and_corners_have_native_resize_targets(qtbot, qapp):
    value = manager(qtbot, qapp)
    w = value.united
    assert w.resize_edges(QPoint(1, 1)) == Qt.LeftEdge | Qt.TopEdge
    assert w.resize_edges(QPoint(w.width()-1, 1)) == Qt.RightEdge | Qt.TopEdge
    assert w.resize_edges(QPoint(1, w.height()-1)) == Qt.LeftEdge | Qt.BottomEdge
    assert w.resize_edges(QPoint(w.width()-1, w.height()-1)) == Qt.RightEdge | Qt.BottomEdge
    assert w.resize_edges(QPoint(w.width()//2, 1)) == Qt.TopEdge
    assert w.resize_edges(QPoint(1, w.height()//2)) == Qt.LeftEdge
    assert not w.resize_edges(QPoint(100, 50))
    value.shutdown()


def test_click_through_updates_native_flags_and_recovers_all_hosts(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.show()
    value.set_click_through(True)
    assert all(w.click_through for w in value.windows.values())
    if sys.platform == "win32" and qapp.platformName() == "windows":
        getter = ctypes.windll.user32.GetWindowLongPtrW
        getter.argtypes, getter.restype = [ctypes.c_void_p, ctypes.c_int], ctypes.c_ssize_t
        assert all(getter(int(w.winId()), -20) & 0x20 for w in value.windows.values())
    value.set_click_through(False)
    if sys.platform == "win32" and qapp.platformName() == "windows":
        assert all(not getter(int(w.winId()), -20) & 0x20 for w in value.windows.values())
    value.shutdown()


def test_personalization_live_and_per_language_does_not_change_main(qtbot, qapp):
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    main_font = window.panels["en"].font_size
    window.personalize_overlay("en")
    dialog = window.visual_dialog
    qtbot.addWidget(dialog)
    dialog.font_size.setValue(26)
    assert style_for(window.settings, "es").font_size == 26
    dialog.linked.setChecked(False)
    dialog.font_size.setValue(30)
    assert style_for(window.settings, "en").font_size == 30
    assert style_for(window.settings, "es").font_size == 26
    assert window.overlays.panels["en"].font_size == 30
    assert window.panels["en"].font_size == main_font
    dialog._colors["text_color"] = "#aaffcc"
    dialog._colors["background_color"] = "#202020"
    dialog.opacity.setValue(50)
    assert window.overlays.panels["en"].foreground == "#aaffcc"
    assert style_for(window.settings, "en").background_opacity == .5
    window.close()


def test_style_and_window_settings_round_trip_and_no_text_saved(tmp_path):
    settings = Settings(overlay_split=True)
    settings.overlay_styles = {"en": OverlayStyle(font_size=25, text_color="#99ffbb").to_dict()}
    settings.overlay_geometries = {"en": [-900, 60, 640, 230], "es": [100, 90, 700, 240]}
    path = tmp_path / "settings.json"
    settings.save(path)
    restored = Settings.load(path)
    assert restored.overlay_split and restored.overlay_geometries == settings.overlay_geometries
    assert style_for(restored, "en").text_color == "#99ffbb"
    assert "captions" not in json.loads(path.read_text())
    assert OverlayStyle.from_dict({"text_color":"red; bad", "font_size":0}).font_size == 14
    assert OverlayStyle.from_dict({"text_color":"red; bad"}).text_color == "#f2f3f5"


def test_existing_overlay_settings_still_control_geometry_and_lines(qtbot, monkeypatch):
    from dual_live_captions import ui
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    window.toggle_overlay()
    class Dialog:
        def __init__(self, *args):
            pass
        def exec(self):
            return QDialog.Accepted
        def result_settings(self):
            return replace(window.settings, overlay_width=800, overlay_lines=10, overlay_position="top")
    monkeypatch.setattr(ui, "SettingsDialog", Dialog)
    window.configure()
    assert window.overlay.width() == 800
    assert window.overlay.y() == QApplication.screens()[0].availableGeometry().y() + 20
    assert style_for(window.settings, "en").max_lines == 10
    window.close()


def test_saved_rect_recovers_removed_monitor_and_negative_coordinates():
    main, left = QRect(0, 0, 1920, 1040), QRect(-1280, 0, 1280, 1024)
    rect = QRect(-1200, 40, 640, 240)
    assert bounded_geometry(rect, [main, left]) == rect
    assert main.contains(bounded_geometry(rect, [main]))
    assert main.contains(bounded_geometry(QRect(1800, 900, 3000, 2000), [main]))


def test_auto_size_has_readable_floor_and_background_alpha_leaves_text_opaque(qtbot, qapp):
    value = manager(qtbot, qapp)
    value.settings.overlay_styles = {lang: OverlayStyle(font_size=30, auto_size=True, background_opacity=.45).to_dict() for lang in ("en", "es")}
    value.apply_settings()
    value.show()
    value.toggle_split()
    w, panel = value.windows["en"], value.panels["en"]
    w.resize(360, 110)
    value.receive(caption(text="Readable captions stay visible"))
    qtbot.waitUntil(lambda: not panel._updating_view)
    assert 16 <= panel.font_size <= 30
    assert w.windowOpacity() == 1.0
    # Surface alpha is independent of glyph opacity.
    w.toolbar.hide()
    img = w.grab().toImage()
    assert 100 <= QColor(img.pixelColor(15, img.height()-15)).alpha() <= 140
    value.shutdown()
