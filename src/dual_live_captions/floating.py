"""Frameless caption windows; the existing ASR only publishes Caption events."""
import ctypes
import sys
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QObject, Signal, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QCursor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QSplitterHandle, QToolButton, QHBoxLayout, QApplication, QAbstractButton, QScrollBar
from .overlay_style import style_for


def bounded_geometry(rect, areas, preferred=0):
    """Logical pixels throughout, including negative monitor coordinates."""
    area = next((a for a in areas if a.contains(rect.center())), areas[min(max(preferred, 0), len(areas) - 1)])
    width, height = min(max(280, rect.width()), area.width()), min(max(92, rect.height()), area.height())
    return QRect(min(max(rect.x(), area.left()), area.right() - width + 1),
                 min(max(rect.y(), area.top()), area.bottom() - height + 1), width, height)


def pointer_geometry(rect, delta, edges, minimum, maximum):
    """Resize from the press rectangle, keeping the opposite edges anchored.

    QRect.right()/bottom() are inclusive; use x+width/y+height for the anchors
    to avoid one-pixel drift on every motion. Screen recovery is not part of a
    pointer gesture, so moving to another monitor never snaps the window back.
    """
    if not edges:
        return rect.translated(delta)
    width, height = rect.width(), rect.height()
    if edges & (Qt.LeftEdge | Qt.RightEdge):
        width += -delta.x() if edges & Qt.LeftEdge else delta.x()
        width = min(maximum.width(), max(minimum.width(), width))
    if edges & (Qt.TopEdge | Qt.BottomEdge):
        height += -delta.y() if edges & Qt.TopEdge else delta.y()
        height = min(maximum.height(), max(minimum.height(), height))
    x = rect.x() + rect.width() - width if edges & Qt.LeftEdge else rect.x()
    y = rect.y() + rect.height() - height if edges & Qt.TopEdge else rect.y()
    return QRect(x, y, width, height)


class Overlay(QWidget):
    split_requested = Signal()
    return_requested = Signal()
    visual_requested = Signal(str)
    hide_requested = Signal(str)
    geometry_changed = Signal()

    def __init__(self, settings, key="united", panels=None):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.settings, self.key = settings, key
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle("Dual Live Captions · Overlay" + (" · " + key.upper() if key != "united" else ""))
        self.setObjectName("captionOverlay")
        self.setStyleSheet("QWidget#captionOverlay {background:transparent;}")
        self.setMouseTracking(True)
        self.click_through = False
        self._ready = False
        self._gesture = None
        self._recover_pending = False
        self.setMinimumSize(280, 92)
        self.resize(960 if key == "united" else 640, 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.caption_splitter = QSplitter()
        self.caption_splitter.setObjectName("captionSplitter")
        self.caption_splitter.setChildrenCollapsible(False)
        self.caption_splitter.setHandleWidth(2)
        self.caption_splitter.setStyleSheet("QSplitter {background:transparent;} QSplitter::handle {background:#46505d;}")
        layout.addWidget(self.caption_splitter)
        if panels is None:
            from .overlay import CaptionPanel
            panels = {lang: CaptionPanel(lang, True, minimal=True) for lang in ("en", "es")}
        self.panels = {}
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("overlayTools")
        self.toolbar.setStyleSheet("QWidget#overlayTools {background:#242a33;border:1px solid #4d5969;border-radius:7px;} QToolButton {background:transparent;color:#edf1f6;border:0;border-radius:4px;padding:3px 6px;font-size:12px;} QToolButton:hover {background:#455166;}")
        row = QHBoxLayout(self.toolbar)
        row.setContentsMargins(3, 2, 3, 2)
        row.setSpacing(1)
        self.move_button = QToolButton()
        self.move_button.setText("⠿")
        self.move_button.setToolTip("Arrastrar para mover")
        self.move_button.setCursor(Qt.SizeAllCursor)
        self.move_button.setFocusPolicy(Qt.NoFocus)
        row.addWidget(self.move_button)
        self.split_button = self._button(row, "Separar", "Separar / unir idiomas", self.split_requested.emit)
        self.visual_button = self._button(row, "Aa", "Personalización", lambda: self.visual_requested.emit(self.key))
        self.return_button = self._button(row, "↗", "Volver a la ventana principal", self.return_requested.emit)
        self.close_button = self._button(row, "×", "Ocultar este overlay", lambda: self.hide_requested.emit(self.key))
        self.toolbar.adjustSize()
        self.toolbar.hide()
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._hide_tools_if_outside)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._settle_geometry)
        self.set_panels(panels)
        self._ready = True
        self.apply_settings()

    def _button(self, row, text, tooltip, action):
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(action)
        row.addWidget(button)
        return button

    def set_panels(self, panels):
        self.panels = panels
        for panel in panels.values():
            self.caption_splitter.addWidget(panel)
            panel.show()
        for widget in (self, *self.findChildren(QWidget)):
            widget.setMouseTracking(True)
            if widget is not self:
                widget.installEventFilter(self)

    def apply_settings(self):
        self.caption_splitter.setOrientation(Qt.Horizontal if self.settings.caption_layout == "columns" else Qt.Vertical)
        self.split_button.setText("Unir" if self.settings.overlay_split else "Separar")
        for lang, panel in self.panels.items():
            panel.apply_visual_style(style_for(self.settings, lang), self.settings.caption_word_limit)
            panel.setVisible(self.settings.overlay_english if lang == "en" else self.settings.overlay_spanish)
        self.update_limits()
        self.toolbar.adjustSize()
        self._position_tools()
        self.update()

    def update_limits(self):
        if self._gesture:
            return
        areas = [s.availableGeometry() for s in QApplication.screens()]
        # Lines describe an initial reading height, never a manual resize cap.
        # Use the largest available monitor dimensions, independent of position.
        self.setMaximumSize(max(a.width() for a in areas), max(a.height() for a in areas))

    def initial_height(self):
        heights = []
        for lang, panel in self.panels.items():
            if panel.isHidden():
                continue
            style = style_for(self.settings, lang)
            font = QFont(style.font_family)
            font.setPixelSize(style.font_size)
            heights.append(QFontMetrics(font).lineSpacing() * style.max_lines + 36)
        return sum(heights) + 14 if self.caption_splitter.orientation() == Qt.Vertical else max(heights, default=260) + 12

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        visible = [(lang, panel) for lang, panel in self.panels.items() if not panel.isHidden()]
        for index, (lang, panel) in enumerate(visible):
            style = style_for(self.settings, lang)
            rect = QRect(panel.mapTo(self, QPoint()), panel.size())
            # Extend the edge panes into the resize gutter, preserving rounded outer corners.
            if len(visible) == 1:
                rect = self.rect().adjusted(1, 1, -1, -1)
            elif self.caption_splitter.orientation() == Qt.Horizontal:
                rect.adjust(-5 if index == 0 else 0, -5, 5 if index == len(visible) - 1 else 0, 5)
            else:
                rect.adjust(-5, -5 if index == 0 else 0, 5, 5 if index == len(visible) - 1 else 0)
            color = QColor(style.background_color)
            color.setAlphaF(style.background_opacity)
            painter.setPen(QPen(QColor(150, 162, 180, 65), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 9, 9)

    def _position_tools(self):
        self.toolbar.move(max(6, self.width() - self.toolbar.width() - 8), 7)
        self.toolbar.raise_()

    def enterEvent(self, event):
        self._leave_timer.stop()
        self.toolbar.show()
        self._position_tools()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._leave_timer.start(250)
        super().leaveEvent(event)

    def _hide_tools_if_outside(self):
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.toolbar.hide()

    def resize_edges(self, point):
        edges = Qt.Edges()
        if point.x() < 7:
            edges |= Qt.LeftEdge
        elif point.x() >= self.width() - 7:
            edges |= Qt.RightEdge
        if point.y() < 7:
            edges |= Qt.TopEdge
        elif point.y() >= self.height() - 7:
            edges |= Qt.BottomEdge
        return edges

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            point = self.mapFromGlobal(event.globalPosition().toPoint())
            if self._mouse_event(event, point, watched):
                return True
        return super().eventFilter(watched, event)

    def _drag_surface(self, watched, point):
        if watched is self.move_button:
            return True
        if isinstance(watched, (QAbstractButton, QScrollBar, QSplitterHandle)):
            return False
        for panel in self.panels.values():
            viewport = panel.scroll.viewport()
            if panel._document and viewport.rect().contains(viewport.mapFrom(self, point)):
                local = panel.text.mapFrom(self, point)
                # Preserve selecting real subtitle text; the unused area of the
                # same label is a draggable empty surface, even in a tall window.
                if panel.text.rect().contains(local) and panel._document.documentLayout().hitTest(QPointF(local), Qt.ExactHit) >= 0:
                    return False
        return True

    def _start_gesture(self, event, edges):
        self.update_limits()
        self._settle_timer.stop()
        self._gesture = event.globalPosition().toPoint(), QRect(self.geometry()), edges
        self.grabMouse()
        event.accept()

    def _apply_gesture(self, position):
        origin, rect, edges = self._gesture
        minimum = self.minimumSize().expandedTo(self.minimumSizeHint())
        self.setGeometry(pointer_geometry(rect, position - origin, edges, minimum, self.maximumSize()))

    def _finish_gesture(self):
        self._gesture = None
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()
        self.unsetCursor()
        if self._recover_pending:
            self._recover_pending = False
            self.recover_to_screens()
        self._settle_timer.start(350)

    def _mouse_event(self, event, point, watched=None):
        if self._gesture:
            if event.type() == QEvent.MouseMove:
                if event.buttons() & Qt.LeftButton:
                    self._apply_gesture(event.globalPosition().toPoint())
                return True
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._apply_gesture(event.globalPosition().toPoint())
                self._finish_gesture()
                return True
        if self.settings.overlay_locked or self.click_through:
            return False
        watched = watched or self
        if isinstance(watched, (QAbstractButton, QScrollBar, QSplitterHandle)) and watched is not self.move_button:
            return False
        edges = self.resize_edges(point)
        if event.type() == QEvent.MouseMove:
            diagonal = edges & (Qt.LeftEdge | Qt.RightEdge) and edges & (Qt.TopEdge | Qt.BottomEdge)
            cursor = (Qt.SizeFDiagCursor if bool(edges & Qt.LeftEdge) == bool(edges & Qt.TopEdge) else Qt.SizeBDiagCursor) if diagonal else Qt.SizeHorCursor if edges & (Qt.LeftEdge | Qt.RightEdge) else Qt.SizeVerCursor if edges else Qt.ArrowCursor
            self.setCursor(cursor)
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and (edges or self._drag_surface(watched, point)):
            # Handle the complete gesture here. QWindow.startSystemMove/Resize
            # was unreliable with these frameless, non-activating Tool windows.
            self._start_gesture(event, edges)
            return True
        return False

    def event(self, event):
        if event.type() == QEvent.UngrabMouse and getattr(self, "_gesture", None):
            self._finish_gesture()
        return super().event(event)

    def hideEvent(self, event):
        if self._gesture:
            self._finish_gesture()
        super().hideEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_event(event, event.position().toPoint())

    def mousePressEvent(self, event):
        if not self._mouse_event(event, event.position().toPoint()):
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._mouse_event(event, event.position().toPoint())

    def mouseDoubleClickEvent(self, event):
        event.accept()  # Never maximize a caption overlay by double-clicking.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._ready:
            self._position_tools()
            if not self._gesture:
                self._settle_timer.start(350)
            self.update()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._ready:
            if not self._gesture:
                self._settle_timer.start(350)

    def _settle_geometry(self):
        if self.isVisible() and not self._gesture:
            # Persistence only: never alter a rectangle chosen with the mouse.
            self.geometry_changed.emit()

    def recover_to_screens(self):
        if self._gesture:
            self._recover_pending = True
            return
        self.update_limits()
        self.setGeometry(bounded_geometry(self.geometry(), [s.availableGeometry() for s in QApplication.screens()], self.settings.overlay_screen))

    def place(self, reset=False):
        areas = [s.availableGeometry() for s in QApplication.screens()]
        saved = None if reset else self.settings.overlay_geometries.get(self.key)
        if saved:
            rect = QRect(*saved)
        else:
            area = areas[min(max(0, self.settings.overlay_screen), len(areas) - 1)]
            initial_width = 960 if self.settings.overlay_width == 1280 else self.settings.overlay_width
            width = min(initial_width if self.key == "united" else min(640, initial_width), area.width() - 32)
            height = min(max(92, self.initial_height()), self.maximumHeight())
            x = area.center().x() - width // 2 + (32 if self.key == "es" else 0)
            y = area.y() + 20 if self.settings.overlay_position == "top" else area.bottom() - height - 20
            if self.key == "es":
                y -= height + 16
            rect = QRect(x, y, width, height)
        self.setGeometry(bounded_geometry(rect, areas, self.settings.overlay_screen))
        self.update_limits()

    def set_click_through(self, value):
        if value and self._gesture:
            self._finish_gesture()
        self.click_through = value
        if sys.platform == "win32":
            user = ctypes.windll.user32
            get_style, set_style = user.GetWindowLongPtrW, user.SetWindowLongPtrW
            get_style.argtypes, get_style.restype = [ctypes.c_void_p, ctypes.c_int], ctypes.c_ssize_t
            set_style.argtypes, set_style.restype = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t
            handle = int(self.winId())
            style = get_style(handle, -20) | 0x08000000 | 0x00080000
            set_style(handle, -20, style | 0x20 if value else style & ~0x20)
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, value)
        if value:
            self.toolbar.hide()

    def receive(self, caption):
        if caption.language in self.panels:
            self.panels[caption.language].receive(caption)

    def closeEvent(self, event):
        event.ignore()
        self.hide_requested.emit(self.key)


class OverlayManager(QObject):
    return_requested = Signal()
    visual_requested = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.united = Overlay(settings)
        self.panels = dict(self.united.panels)
        self.windows = {"united": self.united, "en": Overlay(settings, "en", {}), "es": Overlay(settings, "es", {})}
        self.active = False
        self.persistence_enabled = True
        self._saving = QTimer(self)
        self._saving.setSingleShot(True)
        self._saving.timeout.connect(self.save)
        self._screen_links = set()
        for window in self.windows.values():
            window.split_requested.connect(self.toggle_split)
            window.return_requested.connect(self.return_requested)
            window.visual_requested.connect(self.visual_requested)
            window.hide_requested.connect(self.hide_window)
            window.geometry_changed.connect(self._remember_geometry)
        app = QApplication.instance()
        app.screenAdded.connect(self._connect_screens)
        app.screenRemoved.connect(self.recover_windows)
        self._connect_screens()
        self._attach_panels()

    def _connect_screens(self, *_):
        for screen in QApplication.screens():
            if screen not in self._screen_links:
                screen.availableGeometryChanged.connect(self.recover_windows)
                self._screen_links.add(screen)

    def _remember_geometry(self):
        for key, window in self.windows.items():
            if window.isVisible():
                rect = window.geometry()
                self.settings.overlay_geometries[key] = [rect.x(), rect.y(), rect.width(), rect.height()]
        self._saving.start(500)

    def save(self):
        if not self.persistence_enabled:
            return
        try:
            self.settings.save()
        except OSError:
            # Keep live captioning running on a read-only/full settings disk.
            pass

    def _attach_panels(self):
        for panel in self.panels.values():
            for widget in (panel, *panel.findChildren(QWidget)):
                for window in self.windows.values():
                    widget.removeEventFilter(window)
            panel.setParent(None)
        for window in self.windows.values():
            window.set_panels({})
        if self.settings.overlay_split:
            for lang, panel in self.panels.items():
                self.windows[lang].set_panels({lang: panel})
        else:
            self.united.set_panels(self.panels)
        self.apply_settings()

    def apply_settings(self, reset_geometry=False):
        for window in self.windows.values():
            window.settings = self.settings
            window.apply_settings()
            if reset_geometry:
                window.place(reset=True)
                window.setProperty("placed", True)
        if self.active:
            self.show()

    def receive(self, caption):
        if caption.language in self.panels:
            self.panels[caption.language].receive(caption)

    def isVisible(self):
        return any(w.isVisible() for w in self.windows.values())

    def show(self):
        self.active = True
        for key, window in self.windows.items():
            visible = (key != "united") if self.settings.overlay_split else key == "united"
            if key in ("en", "es"):
                visible = visible and (self.settings.overlay_english if key == "en" else self.settings.overlay_spanish)
            elif not self.settings.overlay_english and not self.settings.overlay_spanish:
                visible = False
            if visible:
                if not window.property("placed"):
                    window.place()
                    window.setProperty("placed", True)
                window.show()
            else:
                window.hide()

    def hide(self):
        self._remember_geometry()
        self.active = False
        for window in self.windows.values():
            window.hide()

    def toggle_split(self):
        was_active = self.active
        self.hide()
        self.settings.overlay_split = not self.settings.overlay_split
        self._attach_panels()
        if was_active:
            self.show()
        self.save()

    def hide_window(self, key):
        if key == "united":
            self.hide()
        else:
            setattr(self.settings, "overlay_english" if key == "en" else "overlay_spanish", False)
            self.windows[key].hide()
            self.save()
        if not self.isVisible():
            self.return_requested.emit()

    def set_click_through(self, value):
        for window in self.windows.values():
            window.set_click_through(value)

    def recover_windows(self, *_):
        for window in self.windows.values():
            window.recover_to_screens()

    def shutdown(self):
        self.hide()
        self._saving.stop()
        self.save()
        for window in self.windows.values():
            window.deleteLater()
