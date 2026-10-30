from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
import json
import os


def data_dir() -> Path:
    path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DualLiveCaptions"
    path.mkdir(parents=True, exist_ok=True)
    return path


PROFILES = {
    "Rápido": dict(model="base", interval=0.55, beam_size=1, min_speech=0.64, silence=0.40, max_window=10.0),
    "Equilibrado": dict(model="small", interval=0.75, beam_size=2, min_speech=0.80, silence=0.48, max_window=14.0),
    "Preciso": dict(model="large-v3-turbo", interval=0.95, beam_size=3, min_speech=0.96, silence=0.58, max_window=18.0),
}


@dataclass
class Settings:
    profile: str = "Equilibrado"
    model: str = "small"
    device: str = "auto"
    compute_type: str = "float16"
    output: str = "default"
    microphone: str = "none"
    system_audio: bool = True
    languages: tuple = ("en", "es")
    interval: float = 0.75
    beam_size: int = 2
    min_speech: float = 0.80
    silence: float = 0.48
    max_window: float = 14.0
    vad_threshold: float = 0.5
    font_size: int = 20
    opacity: float = 0.94
    overlay_lines: int = 20
    overlay_width: int = 1280
    caption_word_limit: int = 500
    caption_layout_version: int = 3
    caption_layout: str = "columns"
    overlay_position: str = "bottom"
    overlay_screen: int = 0
    overlay_locked: bool = False
    overlay_english: bool = True
    overlay_spanish: bool = True
    overlay_split: bool = False
    overlay_styles: dict = field(default_factory=dict)
    overlay_style_linked: bool = True
    overlay_geometries: dict = field(default_factory=dict)
    history_enabled: bool = False
    retention_minutes: int = 60
    start_minimized: bool = False
    hotkey_overlay: str = "Ctrl+Alt+O"
    hotkey_pause: str = "Ctrl+Alt+P"

    def apply_profile(self, profile):
        self.profile = profile
        for key, value in PROFILES[profile].items():
            setattr(self, key, value)

    def validate(self):
        if self.device not in ("auto", "cpu", "cuda"):
            self.device = "auto"
        self.font_size = min(64, max(14, self.font_size))
        self.opacity = min(1, max(0.25, self.opacity))
        self.overlay_lines = min(32, max(1, self.overlay_lines))
        if self.caption_layout not in ("columns", "rows"):
            self.caption_layout = "columns"
        self.overlay_width = min(2400, max(480, self.overlay_width))
        self.caption_word_limit = min(2000, max(100, self.caption_word_limit))
        self.vad_threshold = min(0.95, max(0.1, self.vad_threshold))
        self.interval = min(3.0, max(0.35, self.interval))
        self.max_window = min(24.0, max(6.0, self.max_window))
        self.retention_minutes = min(480, max(1, self.retention_minutes))
        self.languages = tuple(x for x in self.languages if x in ("en", "es")) or ("en", "es")
        from .overlay_style import OverlayStyle
        if not isinstance(self.overlay_styles, dict):
            self.overlay_styles = {}
        self.overlay_styles = {k: OverlayStyle.from_dict(v).to_dict() for k, v in self.overlay_styles.items() if k in ("en", "es")}
        if not isinstance(self.overlay_geometries, dict):
            self.overlay_geometries = {}
        self.overlay_geometries = {k: [int(n) for n in v] for k, v in self.overlay_geometries.items()
                                   if k in ("united", "en", "es") and isinstance(v, (list, tuple)) and len(v) == 4
                                   and all(isinstance(n, (int, float)) and abs(n) < 100000 for n in v)}
        if not self.system_audio and self.microphone == "none":
            self.system_audio = True

    def save(self, path=None):
        self.validate()
        path = Path(path or data_dir() / "settings.json")
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

    @classmethod
    def load(cls, path=None):
        try:
            raw = json.loads(Path(path or data_dir() / "settings.json").read_text(encoding="utf-8"))
            if raw.get("caption_layout_version", 1) < 3:
                if raw.get("font_size", 25) in (25, 28):
                    raw["font_size"] = 20
                if raw.get("overlay_lines", 3) in (3, 5):
                    raw["overlay_lines"] = 20
                if raw.get("overlay_width", 1120) == 1120:
                    raw["overlay_width"] = 1280
                raw["caption_layout_version"] = 3
            result = cls(**{k: v for k, v in raw.items() if k in {f.name for f in fields(cls)}})
            result.validate()
            return result
        except (OSError, ValueError, TypeError):
            return cls()
