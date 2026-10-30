from collections import deque
from dataclasses import replace
from difflib import SequenceMatcher
from bisect import bisect_right
import html
import math
import re
from PySide6.QtCore import Qt, QTimer, QSize, QPointF, QEvent
from PySide6.QtGui import QFont, QFontMetrics, QTextDocument, QColor
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QSizePolicy


class CaptionViewport(QScrollArea):
    """The viewport, rather than its 500-word contents, determines window size."""
    preferred_height = 170
    minimum_height = 80

    def sizeHint(self):
        return QSize(650, self.preferred_height)

    def minimumSizeHint(self):
        return QSize(200, min(self.minimum_height, self.preferred_height))


class CaptionPanel(QFrame):
    def __init__(self, language, compact=False, minimal=False):
        super().__init__()
        self.language = language
        self.compact = compact
        self.minimal = minimal
        self.visual_style = None
        self.foreground = "#f1f4fa"
        self.partial_color = "#91a3bc"
        self.word_limit = 500
        self.confirmed = deque(maxlen=2000)
        self.partial = {}
        self.follow_latest = True
        self._updating_view = False
        self._pending_anchor = None
        self._document = None
        self._html = None
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._restore_view)
        self.setObjectName("captionPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*( (10, 5, 10, 7) if minimal else (14, 10, 14, 10)))
        layout.setSpacing(3 if minimal else 6)
        row = QHBoxLayout()
        tag = QLabel("EN" if language == "en" else "ES")
        tag.setObjectName("languageTag")
        tag.setFixedSize(32, 26)
        tag.setAlignment(Qt.AlignCenter)
        self.tag = tag
        if minimal:
            tag.setFixedSize(22, 17)
            tag.setStyleSheet("background:transparent;color:#a7bbd5;font-size:10px;font-weight:600;border:0;")
        title = QLabel("ENGLISH" if language == "en" else "ESPAÑOL")
        title.setObjectName("panelTitle")
        row.addWidget(tag)
        row.addWidget(title)
        row.addStretch()
        self.source_label = QLabel("Audio original")
        self.source_label.setObjectName("muted")
        row.addWidget(self.source_label)
        self.follow_state = QLabel("En vivo")
        self.follow_state.setObjectName("captionFollowState")
        self.follow_state.setStyleSheet("color:#94d4b4;font-size:11px;")
        row.addWidget(self.follow_state)
        self.latest_button = QPushButton("↓ Lo último")
        self.latest_button.setObjectName("latestCaptions")
        self.latest_button.setFocusPolicy(Qt.NoFocus)
        self.latest_button.setStyleSheet("font-size:11px;padding:4px 8px;min-width:74px;")
        self.latest_button.setEnabled(False)
        self.latest_button.clicked.connect(self.jump_to_latest)
        row.addWidget(self.latest_button)
        if minimal:
            title.hide()
            self.source_label.hide()
            self.follow_state.setStyleSheet("font-size:10px;color:#8293a8;")
            self.latest_button.setStyleSheet("font-size:10px;padding:0 5px;min-width:60px;background:transparent;border:0;")
            self.latest_button.hide()
            # Keep the follow marker exposed to assistive readers/comparison.
            self.follow_state.setText("En vivo")
        layout.addLayout(row)
        self.scroll = CaptionViewport()
        self.scroll.setObjectName("captionScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {background:transparent;border:0;}
            QScrollArea > QWidget > QWidget {background:transparent;border:0;}
            QScrollBar:vertical {background:#121925;width:13px;border:0;margin:0;}
            QScrollBar::handle:vertical {background:#607693;min-height:32px;border-radius:6px;}
            QScrollBar::handle:vertical:hover {background:#91acd0;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
        """)
        if minimal:
            self.scroll.minimum_height = 24
            self.scroll.viewport().setAutoFillBackground(False)
            self.scroll.viewport().setStyleSheet("background:transparent;")
            self.setStyleSheet("QFrame#captionPanel {background:transparent;border:0;border-radius:0;} QLabel {background:transparent;}")
            self.scroll.setStyleSheet("""
                QScrollArea, QScrollArea > QWidget > QWidget {background:transparent;border:0;}
                QScrollBar:vertical {background:transparent;width:7px;border:0;}
                QScrollBar::handle:vertical {background:#647080;min-height:24px;border-radius:3px;}
                QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
                QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
            """)
        self.text = QLabel()
        self.text.setTextFormat(Qt.RichText)
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text.setFocusPolicy(Qt.NoFocus)
        self.text.setSizePolicy(QSizePolicy.Ignored if minimal else QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.text.setMargin(0)
        self.scroll.setWidget(self.text)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.verticalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.scroll.verticalScrollBar().valueChanged.connect(self._scroll_changed)
        self.scroll.verticalScrollBar().sliderPressed.connect(lambda: self._set_follow(False))
        self.scroll.verticalScrollBar().sliderReleased.connect(self._scroll_released)
        layout.addWidget(self.scroll, 1)
        self.font_size = 20
        self.lines = 20
        self.render()

    def configure(self, size, lines, word_limit=500):
        self.font_size, self.lines = size, lines
        self.word_limit = max(100, min(2000, int(word_limit)))
        font = QFont("Segoe UI")
        font.setPixelSize(size)
        self.text.setFont(font)
        self.text.setStyleSheet(f"font-size:{size}px; border:0;")
        self.scroll.preferred_height = QFontMetrics(font).lineSpacing() * lines + 8
        self.scroll.updateGeometry()
        self._trim_confirmed()
        self.render()
        self._reflow()

    def apply_visual_style(self, style, word_limit=500):
        """Overlay only. The main caption panels retain their existing design."""
        self.visual_style = style
        self.foreground = style.text_color
        color, background = QColor(style.text_color), QColor(style.background_color)
        self.partial_color = QColor(*[round(color.getRgb()[i] * .65 + background.getRgb()[i] * .35) for i in range(3)]).name()
        self.configure(style.font_size, style.max_lines, word_limit)
        self.fit_font()
        self.render()

    def fit_font(self):
        if not self.visual_style:
            return
        style = self.visual_style
        size = style.font_size
        if style.auto_size:
            # Fit a few readable lines, never try to squeeze all 500 words.
            target_lines = min(3, style.max_lines)
            available = max(1, self.scroll.viewport().height())
            size = max(min(16, size), min(size, int(available / target_lines / 1.35)))
        font = QFont(style.font_family)
        font.setPixelSize(size)
        self.font_size = size
        self.text.setFont(font)
        family = style.font_family.replace("\\", "").replace("'", "").replace(";", "")
        self.text.setStyleSheet(f"background:transparent;border:0;font-size:{size}px;font-family:'{family}';")
        self._reflow()

    def _trim_confirmed(self):
        extra = sum(len(c.text.split()) for c in self.confirmed) - self.word_limit
        while extra > 0 and self.confirmed:
            first = self.confirmed.popleft()
            words = first.text.split()
            if len(words) > extra:
                self.confirmed.appendleft(replace(first, text=" ".join(words[extra:])))
                break
            extra -= len(words)

    def receive(self, caption):
        if caption.language != self.language:
            return
        if caption.final and caption.text:
            if self.confirmed and caption.source == self.confirmed[-1].source and caption.start < self.confirmed[-1].end + .85:
                prev = self.confirmed.pop()
                caption = replace(caption, text=prev.text + " " + caption.text, start=prev.start)
            self.confirmed.append(caption)
            self._trim_confirmed()
        elif not caption.final:
            self.partial[caption.source] = " ".join(caption.text.split()[-self.word_limit:])
        self.render()

    def clear(self):
        self.confirmed.clear()
        self.partial.clear()
        self._set_follow(True)
        self.render()

    def render(self):
        partial = " ".join(" ".join(self.partial.values()).split()[-self.word_limit:])
        budget = self.word_limit - len(partial.split())
        paragraphs = []
        for caption in reversed(self.confirmed):
            if budget <= 0:
                break
            words = caption.text.split()[-budget:]
            budget -= len(words)
            paragraphs.append(html.escape(" ".join(words)))
        paragraphs.reverse()
        if partial:
            tail = '<span style="color:' + self.partial_color + '">' + html.escape(partial) + '</span>'
            if paragraphs:
                paragraphs[-1] += " " + tail
            else:
                paragraphs.append(tail)
        if paragraphs:
            content = "".join('<p style="margin:0 0 4px 0;color:' + self.foreground + '">' + p + '</p>' for p in paragraphs)
        else:
            content = '<span style="color:#697386">' + ("Waiting for English speech…" if self.language == "en" else "Esperando voz en español…") + '</span>'
        if content != self._html:
            self._begin_update()
            self._html = content
            self.text.setText(content)
            self._reflow()
        sources = {c.source for c in list(self.confirmed)[-3:]}
        self.source_label.setText(" + ".join("Micrófono" if s == "microphone" else "Sistema" for s in sorted(sources)) or "Audio original")

    def _set_follow(self, value):
        self.follow_latest = value
        self.follow_state.setText("En vivo" if value else "Releyendo")
        self.follow_state.setStyleSheet(f"color:{'#94d4b4' if value else '#dfbe83'};font-size:11px;")
        self.latest_button.setEnabled(not value)
        if self.minimal:
            self.latest_button.setVisible(not value)

    def _scroll_changed(self, value):
        if not self._updating_view:
            bar = self.scroll.verticalScrollBar()
            self._set_follow(value >= bar.maximum() - 2 and not bar.isSliderDown())

    def _scroll_released(self):
        bar = self.scroll.verticalScrollBar()
        self._set_follow(bar.value() >= bar.maximum() - 2)

    def jump_to_latest(self):
        self._set_follow(True)
        self._pending_anchor = None
        self._updating_view = True
        self._layout_timer.start(0)

    def _begin_update(self):
        if not self._updating_view:
            self._pending_anchor = self._capture_anchor() if not self.follow_latest else None
        self._updating_view = True

    def _capture_anchor(self):
        if self._document is None:
            return None
        document = self._document
        spans = list(re.finditer(r"\S+", document.toPlainText()))
        if not spans:
            return None
        value = self.scroll.verticalScrollBar().value()
        position = document.documentLayout().hitTest(QPointF(1, value + 1), Qt.FuzzyHit)
        index = max(0, bisect_right([s.start() for s in spans], position) - 1)
        y = self._word_y(document, spans[index].start())
        return [s.group() for s in spans], index, value - y

    @staticmethod
    def _word_y(document, position):
        block = document.findBlock(position)
        line = block.layout().lineForTextPosition(position - block.position())
        return document.documentLayout().blockBoundingRect(block).top() + (line.y() if line.isValid() else 0)

    def _reflow(self):
        if self._html is None:
            return
        self._begin_update()
        width = max(100, self.scroll.viewport().width())
        doc = QTextDocument()
        doc.setDefaultFont(self.text.font())
        doc.setDocumentMargin(0)
        doc.setHtml(self._html)
        doc.setTextWidth(width)
        self._document = doc
        self.text.setMinimumHeight(max(QFontMetrics(self.text.font()).lineSpacing(), math.ceil(doc.size().height())))
        self._layout_timer.start(0)

    def _restore_view(self):
        bar = self.scroll.verticalScrollBar()
        target = bar.maximum() if self.follow_latest else bar.value()
        if not self.follow_latest and self._pending_anchor and self._document:
            old_words, old_index, offset = self._pending_anchor
            spans = list(re.finditer(r"\S+", self._document.toPlainText()))
            matcher = SequenceMatcher(None, old_words, [s.group() for s in spans], autojunk=False)
            match = next((b for b in matcher.get_matching_blocks() if b.a <= old_index < b.a + b.size), None)
            target = self._word_y(self._document, spans[match.b + old_index - match.a].start()) + offset if match else 0
        bar.setValue(max(0, min(bar.maximum(), round(target))))
        self._pending_anchor = None
        self._updating_view = False

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize:
            self.fit_font() if self.visual_style else self._reflow()
        return super().eventFilter(watched, event)


# Keep the existing import path used by callers and tests.
from .floating import Overlay  # noqa: E402,F401
