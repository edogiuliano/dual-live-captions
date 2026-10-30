"""Silent UI verification with generic text. Never plays or records audio."""
import json
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontMetrics
from . import __version__
from .subtitles import Caption


def install(app, window, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    window.setWindowTitle("Dual Live Captions · Verificación visual")
    manager = window.overlays
    manager.persistence_enabled = False
    checks = {}
    report = {"version": __version__, "kind": "silent UI; generic text; no ASR/audio", "checks": checks}
    timer = QTimer(window)
    timer.setSingleShot(True)
    original = dict(manager.panels)
    original_main_size = window.size()

    def send(lang, text, start):
        value = Caption(str(start), "system", lang, text, start, start + 1, True)
        window.panels[lang].receive(value)
        manager.receive(value)

    def fail_safe(callback):
        def execute():
            try:
                callback()
            except Exception as exc:
                report["error_type"] = type(exc).__name__
                report["all_passed"] = False
                conclude()
        return execute

    def later(callback, ms=350):
        QTimer.singleShot(ms, fail_safe(callback))

    def fill():
        for i in range(35):
            send("en", "Good morning. We can read the conversation and scroll back while the new captions keep arriving.", i * 3)
            send("es", "Buen día. Podemos leer la conversación y volver hacia atrás mientras siguen llegando los subtítulos nuevos.", i * 3)
        window.toggle_overlay()
        later(united)

    def united():
        checks["main_completely_hidden"] = not window.isVisible()
        checks["united_visible"] = manager.united.isVisible()
        checks["compact_default_height"] = manager.united.height() <= 300
        checks["no_asr_started"] = window.process is None
        for lang, panel in manager.panels.items():
            checks[lang + "_500_words"] = len(panel._document.toPlainText().split()) == 500
            bar = panel.scroll.verticalScrollBar()
            checks[lang + "_scrolls_and_follows"] = bar.maximum() > 0 and bar.value() == bar.maximum()
        manager.united.toolbar.hide()
        manager.united.grab().save(str(output.with_name(output.stem + "-united.png")))
        manager.united.toolbar.show()
        manager.united.grab().save(str(output.with_name(output.stem + "-controls.png")))
        manager.united.toolbar.hide()
        before = {k: p.text.text() for k, p in manager.panels.items()}
        manager.toggle_split()
        checks["same_panel_objects_after_split"] = manager.panels == original
        checks["same_text_after_split"] = before == {k: p.text.text() for k, p in manager.panels.items()}
        later(separate)

    def separate():
        en, es = manager.windows["en"], manager.windows["es"]
        checks["two_independent_windows"] = en.isVisible() and es.isVisible() and not manager.united.isVisible()
        es_before = es.geometry()
        en.move(en.x() - 35, en.y() - 35)
        en.resize(760, 235)
        checks["english_resize_does_not_move_spanish"] = es.geometry() == es_before
        for lang, w in (("en", en), ("es", es)):
            w.toolbar.hide()
            w.grab().save(str(output.with_name(output.stem + "-" + lang + ".png")))
        later(begin_reading)

    def begin_reading():
        panel = manager.panels["en"]
        panel.scroll.verticalScrollBar().setValue(panel.scroll.verticalScrollBar().maximum() // 2)
        send("en", "The reader keeps their place while this new sentence arrives.", 120)
        later(reading)

    def reading():
        panel = manager.panels["en"]
        checks["reading_not_forced_down"] = not panel.follow_latest
        checks["return_to_live_available"] = panel.latest_button.isVisible() and panel.latest_button.isEnabled()
        panel.latest_button.click()
        window.personalize_overlay("en")
        dialog = window.visual_dialog
        dialog.linked.setChecked(False)
        dialog.font_size.setValue(22)
        dialog._colors["text_color"] = "#d9f3eb"
        dialog.opacity.setValue(85)
        checks["live_style_applied"] = manager.panels["en"].foreground == "#d9f3eb"
        checks["spanish_style_independent"] = manager.panels["es"].foreground != "#d9f3eb"
        later(personalized)

    def personalized():
        window.visual_dialog.grab().save(str(output.with_name(output.stem + "-personalization.png")))
        window.visual_dialog.close()
        # A second installed app can own the recovery hotkey during this check.
        # Test native flags directly, then immediately invoke the recovery route.
        manager.set_click_through(True)
        checks["click_through_all_windows"] = all(w.click_through for w in manager.windows.values())
        window.unlock()
        checks["existing_recovery_disables_click_through"] = not any(w.click_through for w in manager.windows.values())
        panel = manager.panels["en"]
        checks["returned_to_latest"] = panel.follow_latest
        checks["retained_after_resize_and_style"] = len(panel._document.toPlainText().split()) == 500
        report["screens"] = []
        for index, screen in enumerate(app.screens()):
            manager.settings.overlay_screen = index
            manager.settings.overlay_geometries.pop("en", None)
            manager.windows["en"].place()
            report["screens"].append({"name": screen.name(), "dpr": screen.devicePixelRatio(), "inside": screen.availableGeometry().contains(manager.windows["en"].frameGeometry())})
        checks["placement_on_available_monitors"] = all(s["inside"] for s in report["screens"])
        manager.hide_window("en")
        checks["spanish_can_remain_alone"] = manager.windows["es"].isVisible() and not manager.windows["en"].isVisible()
        manager.settings.overlay_english = True
        manager.toggle_split()
        later(finish)

    def finish():
        checks["reunited"] = manager.united.isVisible() and all(p.window() is manager.united for p in manager.panels.values())
        checks["main_still_hidden"] = not window.isVisible()
        manager.united.return_button.click()
        checks["return_button_restores_main"] = window.isVisible() and not manager.isVisible()
        checks["main_design_unchanged"] = all(p.font_size == 20 for p in window.panels.values()) and window.size() == original_main_size
        checks["no_asr_created_by_operations"] = window.process is None
        report["viewports"] = {lang: {"width": p.scroll.viewport().width(), "height": p.scroll.viewport().height(), "font_px": p.font_size, "visible_line_heights": round(p.scroll.viewport().height() / QFontMetrics(p.text.font()).lineSpacing(), 1)} for lang, p in manager.panels.items()}
        window.grab().save(str(output.with_suffix(".png")))
        report["all_passed"] = all(checks.values())
        conclude()

    def conclude():
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        QTimer.singleShot(600, lambda: (window.close(), app.quit()))

    timer.timeout.connect(fail_safe(fill))
    timer.start(500)
    return timer
