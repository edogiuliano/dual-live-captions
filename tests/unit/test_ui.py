from dual_live_captions.settings import Settings
from dual_live_captions.subtitles import Caption
from dual_live_captions.ui import MainWindow, STYLE, SettingsDialog


def test_ui_controls_panels_overlay_and_privacy(qtbot, qapp):
    qapp.setStyleSheet(STYLE)
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    window.show()
    assert window.start_button.isEnabled()
    assert not window.pause_button.isEnabled()
    assert not window.stop_button.isEnabled()
    window.set_state("running")
    assert not window.start_button.isEnabled()
    assert window.pause_button.isEnabled()
    assert window.stop_button.isEnabled()
    caption = Caption("a", "system", "en", "Hello world", 0, 1, True)
    window.panels["en"].receive(caption)
    assert "Hello world" in window.panels["en"].text.text()
    assert "Hello world" not in window.panels["es"].text.text()
    window.toggle_overlay()
    assert window.overlay.isVisible()
    window.overlay.receive(caption)
    window.through.setChecked(True)
    window.unlock()
    assert not window.overlay.click_through
    assert not window.history.enabled
    window.set_state("stopped")
    window.close()


def test_settings_profile_changes_model_and_real_values(qtbot):
    dialog = SettingsDialog(Settings(), [], [])
    qtbot.addWidget(dialog)
    dialog.widgets["profile"].setCurrentIndex(0)
    settings = dialog.result_settings()
    assert settings.model == "base"
    assert settings.interval == .55
    assert settings.beam_size == 1


def test_paragraph_panels_get_most_of_the_window(qtbot, qapp):
    qapp.setStyleSheet(STYLE)
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    window.resize(1280, 980)
    window.show()
    qtbot.waitUntil(lambda: window.panels["en"].scroll.viewport().height() > 650)
    views = [p.scroll.viewport() for p in window.panels.values()]
    assert all(v.width() >= 550 for v in views)
    assert all(v.height() >= 650 for v in views)
    occupied = sum(v.width() * v.height() for v in views)
    assert occupied / (window.centralWidget().width() * window.centralWidget().height()) >= .70
    assert all(p.font_size == 20 for p in window.panels.values())
    window.close()


def test_stacked_view_can_be_selected_without_restarting_capture(qtbot, monkeypatch):
    from PySide6.QtCore import Qt
    monkeypatch.setattr(Settings, "save", lambda *_: None)
    window = MainWindow(Settings(), scan=False)
    qtbot.addWidget(window)
    window.resize(1280, 980)
    window.show()
    window.layout_combo.setCurrentIndex(window.layout_combo.findData("rows"))
    qtbot.waitUntil(lambda: window.panels["en"].scroll.viewport().width() > 1100)
    assert window.caption_splitter.orientation() == Qt.Vertical
    assert all(p.scroll.viewport().height() >= 320 for p in window.panels.values())
    assert window.process is None
    window.close()
