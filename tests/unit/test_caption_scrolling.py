import json
import re
from PySide6.QtCore import QPointF, Qt
from dual_live_captions.overlay import CaptionPanel, Overlay
from dual_live_captions.settings import Settings
from dual_live_captions.subtitles import Caption
from dual_live_captions.ui import STYLE


def caption(text, start=0, final=True, source="system"):
    return Caption(str(start), source, "en", text, start, start + 1, final)


def panel(qtbot, qapp):
    qapp.setStyleSheet(STYLE)
    value = CaptionPanel("en", compact=True)
    value.configure(28, 5)
    value.resize(700, 280)
    qtbot.addWidget(value)
    value.show()
    return value


def words(value):
    return value._document.toPlainText().split()


def first_visible_word(value):
    doc = value._document
    pos = doc.documentLayout().hitTest(QPointF(2, value.scroll.verticalScrollBar().value() + 2), Qt.FuzzyHit)
    spans = list(re.finditer(r"\S+", doc.toPlainText()))
    before = [s.group() for s in spans if s.start() <= pos]
    return before[-1] if before else spans[0].group()


def test_history_is_500_words_and_scrolls_to_latest(qtbot, qapp):
    value = panel(qtbot, qapp)
    value.receive(caption(" ".join(f"word{i}" for i in range(800))))
    qtbot.waitUntil(lambda: not value._updating_view)
    bar = value.scroll.verticalScrollBar()
    assert len(words(value)) == 500
    assert words(value)[0] == "word300"
    assert words(value)[-1] == "word799"
    assert bar.maximum() > 0
    assert bar.value() == bar.maximum()
    assert value.follow_latest
    assert sum(len(c.text.split()) for c in value.confirmed) == 500


def test_single_speaker_can_keep_more_than_old_150_word_limit(qtbot, qapp):
    value = panel(qtbot, qapp)
    value.receive(caption(" ".join(f"a{i}" for i in range(180)), 0))
    value.receive(caption(" ".join(f"a{i}" for i in range(180, 260)), 1.1))
    assert len(words(value)) == 260


def test_reading_older_text_does_not_jump_when_new_caption_arrives(qtbot, qapp):
    value = panel(qtbot, qapp)
    value.receive(caption(" ".join(f"word{i}" for i in range(300))))
    qtbot.waitUntil(lambda: not value._updating_view)
    bar = value.scroll.verticalScrollBar()
    bar.setValue(bar.maximum() // 3)
    before = first_visible_word(value)
    assert not value.follow_latest
    value.receive(caption("new words arriving while the reader looks back", 3))
    qtbot.waitUntil(lambda: not value._updating_view)
    assert first_visible_word(value) == before
    assert not value.follow_latest
    assert value.latest_button.isEnabled()
    assert value.follow_state.text() == "Releyendo"
    value.latest_button.click()
    qtbot.waitUntil(lambda: not value._updating_view)
    assert value.follow_latest
    assert bar.value() == bar.maximum()


def test_reading_anchor_survives_removal_of_oldest_100_words(qtbot, qapp):
    value = panel(qtbot, qapp)
    value.receive(caption(" ".join(f"word{i}" for i in range(500))))
    qtbot.waitUntil(lambda: not value._updating_view)
    bar = value.scroll.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    before = first_visible_word(value)
    before_pos = value._document.toPlainText().index(before)
    before_offset = value._word_y(value._document, before_pos) - bar.value()
    value.receive(caption(" ".join(f"word{i}" for i in range(500, 600)), .5))
    qtbot.waitUntil(lambda: not value._updating_view)
    assert len(words(value)) == 500
    assert words(value)[0] == "word100"
    after_pos = value._document.toPlainText().index(before)
    after_offset = value._word_y(value._document, after_pos) - bar.value()
    # Wrapping can put two earlier words on the same line after a prefix is
    # removed; the reader's actual anchor must remain at the same vertical spot.
    assert abs(after_offset - before_offset) <= 2
    assert not value.follow_latest


def test_partial_does_not_exceed_view_budget_and_confirmed_remains_stable(qtbot, qapp):
    value = panel(qtbot, qapp)
    value.receive(caption(" ".join(f"confirmed{i}" for i in range(500))))
    original = [c.text for c in value.confirmed]
    value.receive(caption(" ".join(f"partial{i}" for i in range(30)), 1, False))
    assert len(words(value)) == 500
    assert words(value)[-1] == "partial29"
    assert [c.text for c in value.confirmed] == original
    value.receive(caption("", 2, False))
    assert words(value)[0] == "confirmed0"


def test_old_layout_migrates_but_custom_font_is_preserved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"font_size": 25, "overlay_lines": 3, "history_enabled": False}))
    result = Settings.load(path)
    assert (result.font_size, result.overlay_lines, result.overlay_width, result.caption_word_limit) == (20, 20, 1280, 500)
    assert result.caption_layout == "columns"
    assert not result.history_enabled
    path.write_text(json.dumps({"font_size": 38, "overlay_lines": 7}))
    result = Settings.load(path)
    assert result.font_size == 38 and result.overlay_lines == 7


def test_overlay_defaults_are_compact_and_stay_in_selected_screen(qtbot):
    overlay = Overlay(Settings())
    qtbot.addWidget(overlay)
    assert overlay.width() == 960
    assert overlay.height() <= 300
    overlay.place()
    from PySide6.QtWidgets import QApplication
    assert QApplication.screens()[0].availableGeometry().contains(overlay.frameGeometry().center())
