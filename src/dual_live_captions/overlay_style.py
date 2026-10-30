"""Small, serializable visual preferences. No dependency on audio or ASR."""
from dataclasses import asdict, dataclass, fields
import re


@dataclass
class OverlayStyle:
    text_color: str = "#f2f3f5"
    font_size: int = 20
    font_family: str = "Segoe UI"
    background_color: str = "#17191e"
    background_opacity: float = .90
    max_lines: int = 8
    auto_size: bool = False

    def validate(self):
        for name, fallback in (("text_color", "#f2f3f5"), ("background_color", "#17191e")):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                setattr(self, name, fallback)
        self.font_size = min(56, max(14, int(self.font_size)))
        self.max_lines = min(32, max(1, int(self.max_lines)))
        self.background_opacity = min(1., max(.15, float(self.background_opacity)))
        self.font_family = str(self.font_family).strip()[:100] or "Segoe UI"
        self.auto_size = bool(self.auto_size)
        return self

    @classmethod
    def from_dict(cls, raw):
        try:
            return cls(**{k: v for k, v in raw.items() if k in {f.name for f in fields(cls)}}).validate()
        except (TypeError, ValueError, AttributeError, OverflowError):
            return cls()

    def to_dict(self):
        return asdict(self.validate())


def style_for(settings, language):
    defaults = OverlayStyle(font_size=settings.font_size, background_opacity=settings.opacity)
    return OverlayStyle.from_dict(settings.overlay_styles.get(language, defaults.to_dict()))
