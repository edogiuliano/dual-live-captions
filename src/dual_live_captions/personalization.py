"""Live overlay appearance editor. Changes never touch engine settings."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                              QCheckBox, QComboBox, QPushButton, QSpinBox, QFontComboBox,
                              QSlider, QColorDialog, QFrame)
from .overlay_style import style_for
from .overlay import CaptionPanel
from .subtitles import Caption


class PersonalizationDialog(QDialog):
    changed = Signal()

    def __init__(self, settings, language="united", parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Personalización · Overlay")
        self.resize(540, 580)
        self._loading = False
        self._colors = {}
        layout = QVBoxLayout(self)
        heading = QLabel("Subtítulos a tu medida")
        heading.setStyleSheet("font-size:20px;font-weight:600;background:transparent;")
        layout.addWidget(heading)
        description = QLabel("Los cambios se ven al instante y se guardan automáticamente.")
        description.setObjectName("muted")
        layout.addWidget(description)
        self.linked = QCheckBox("Usar el mismo aspecto para inglés y español")
        self.linked.setChecked(settings.overlay_style_linked)
        layout.addWidget(self.linked)
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.language = QComboBox()
        self.language.addItem("English · EN", "en")
        self.language.addItem("Español · ES", "es")
        self.language.setCurrentIndex(1 if language == "es" else 0)
        self.language.setEnabled(not self.linked.isChecked())
        form.addRow("Idioma", self.language)
        self.font_family = QFontComboBox()
        form.addRow("Tipo de fuente", self.font_family)
        self.font_size = QSpinBox()
        self.font_size.setRange(14, 56)
        self.font_size.setSuffix(" px")
        form.addRow("Tamaño", self.font_size)
        self.text_color = QPushButton()
        self.background_color = QPushButton()
        form.addRow("Color del texto", self.text_color)
        form.addRow("Color del fondo", self.background_color)
        opacity_row = QHBoxLayout()
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(15, 100)
        self.opacity_label = QLabel()
        opacity_row.addWidget(self.opacity, 1)
        opacity_row.addWidget(self.opacity_label)
        form.addRow("Opacidad del fondo", opacity_row)
        self.lines = QSpinBox()
        self.lines.setRange(1, 32)
        self.lines.setToolTip("Altura de referencia inicial. Arrastrá los bordes para mostrar tantas líneas como permita la ventana.")
        form.addRow("Líneas iniciales", self.lines)
        self.auto_size = QCheckBox("Adaptar dentro de un tamaño legible (mínimo 16 px)")
        form.addRow("Tamaño automático", self.auto_size)
        layout.addLayout(form)
        label = QLabel("Vista previa · texto de ejemplo")
        label.setObjectName("muted")
        layout.addWidget(label)
        self.preview_surface = QFrame()
        self.preview_surface.setObjectName("previewSurface")
        preview_layout = QVBoxLayout(self.preview_surface)
        preview_layout.setContentsMargins(2, 2, 2, 2)
        self.preview = CaptionPanel("en", True, minimal=True)
        preview_layout.addWidget(self.preview)
        self.preview_surface.setMinimumHeight(135)
        self.preview_surface.setMaximumHeight(165)
        layout.addWidget(self.preview_surface, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.close)
        layout.addWidget(close, alignment=Qt.AlignRight)
        self.text_color.clicked.connect(lambda: self.choose_color("text_color"))
        self.background_color.clicked.connect(lambda: self.choose_color("background_color"))
        self.font_family.currentFontChanged.connect(self.update_style)
        for control in (self.font_size, self.opacity, self.lines):
            control.valueChanged.connect(self.update_style)
        self.auto_size.toggled.connect(self.update_style)
        self.linked.toggled.connect(self.change_linked)
        self.language.currentIndexChanged.connect(self.load_style)
        self.load_style()

    def load_style(self, *_):
        self._loading = True
        style = style_for(self.settings, self.language.currentData())
        self.font_family.setCurrentFont(QFont(style.font_family))
        self.font_size.setValue(style.font_size)
        self.opacity.setValue(round(style.background_opacity * 100))
        self.lines.setValue(style.max_lines)
        self.auto_size.setChecked(style.auto_size)
        self._colors = {"text_color": style.text_color, "background_color": style.background_color}
        self._loading = False
        self.update_preview(style)

    def change_linked(self, value):
        self.settings.overlay_style_linked = value
        self.language.setEnabled(not value)
        if value:
            self.update_style()
        else:
            self.changed.emit()

    def choose_color(self, name):
        color = QColorDialog.getColor(QColor(self._colors[name]), self, "Color de subtítulos" if name == "text_color" else "Color de fondo")
        if color.isValid():
            self._colors[name] = color.name()
            self.update_style()

    def update_style(self, *_):
        if self._loading:
            return
        lang = self.language.currentData()
        style = style_for(self.settings, lang)
        style.font_family = self.font_family.currentFont().family()
        style.font_size = self.font_size.value()
        style.text_color = self._colors["text_color"]
        style.background_color = self._colors["background_color"]
        style.background_opacity = self.opacity.value() / 100
        style.max_lines = self.lines.value()
        style.auto_size = self.auto_size.isChecked()
        for target in (("en", "es") if self.linked.isChecked() else (lang,)):
            self.settings.overlay_styles[target] = style.to_dict()
        self.update_preview(style)
        self.changed.emit()

    def update_preview(self, style):
        self.opacity_label.setText(f"{round(style.background_opacity * 100)}%")
        for name in ("text_color", "background_color"):
            button = getattr(self, name)
            button.setText(self._colors[name].upper())
            button.setStyleSheet(f"border-left:12px solid {self._colors[name]};")
        background = QColor(style.background_color)
        self.preview_surface.setStyleSheet(f"QFrame#previewSurface {{background:rgba({background.red()},{background.green()},{background.blue()},{round(style.background_opacity * 255)});border:1px solid #485264;border-radius:9px;}}")
        lang = self.language.currentData()
        self.preview.language = lang
        self.preview.tag.setText(lang.upper())
        self.preview.clear()
        text = "Good morning. Keep the conversation in view while the captions arrive. Resize the overlay to read more context." if lang == "en" else "Buen día. Seguí la conversación mientras llegan los subtítulos. Agrandá el overlay para leer más contexto."
        self.preview.receive(Caption("preview", "system", lang, text, 0, 1, True))
        self.preview.apply_visual_style(style)
