from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re


def normalize(text):
    return re.sub(r"[^\wáéíóúüñ]", "", text.casefold())


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    probability: float = 1.0


@dataclass(frozen=True)
class Caption:
    id: str
    source: str
    language: str
    text: str
    start: float
    end: float
    final: bool
    published: float = 0.0


class Agreement:
    """Append-only confirmed words; replaceable tail, aligned by audio time."""
    def __init__(self):
        self.previous = []
        self.committed_end = -1.0
        self.recent = deque(maxlen=16)

    def update(self, words, final=False, audio_end=float("inf")):
        candidates = [w for w in words if w.end > self.committed_end + 0.06 and normalize(w.text)]
        # Reject repeated overlap at a cut boundary, but allow actual later repetition.
        while candidates and self.recent and candidates[0].start < self.committed_end + 0.12 and normalize(candidates[0].text) == self.recent[-1]:
            candidates.pop(0)
        count = len(candidates) if final else 0
        if not final:
            for old, new in zip(self.previous, candidates):
                if normalize(old.text) != normalize(new.text) or abs(old.start - new.start) > 0.8 or new.end > audio_end - 0.24:
                    break
                count += 1
        committed = candidates[:count]
        if committed:
            self.committed_end = committed[-1].end
            self.recent.extend(normalize(w.text) for w in committed)
        self.previous = candidates[count:]
        return committed, candidates[count:]


class History:
    """Opt-in memory only. Files are written exclusively by explicit export."""
    def __init__(self, enabled=False, retention_minutes=60, max_items=10000):
        self.enabled = enabled
        self.retention_minutes = retention_minutes
        self.items = deque(maxlen=max_items)

    def add(self, caption):
        if not self.enabled or not caption.final:
            return
        self.items.append(caption)
        cutoff = caption.end - self.retention_minutes * 60
        while self.items and self.items[0].end < cutoff:
            self.items.popleft()

    def clear(self):
        self.items.clear()

    def ordered(self):
        return sorted(self.items, key=lambda c: (c.start, c.end, c.source))

    def export(self, path):
        path = Path(path)
        items = self.ordered()
        if path.suffix.lower() == ".json":
            content = json.dumps({"schema": 1, "captions": [asdict(c) for c in items]}, ensure_ascii=False, indent=2)
        elif path.suffix.lower() == ".srt":
            content = "\n\n".join(f"{i}\n{srt_time(c.start)} --> {srt_time(max(c.end, c.start + .1))}\n[{c.language.upper()} · {c.source}] {c.text}" for i, c in enumerate(items, 1)) + "\n"
        else:
            content = "\n".join(f"[{srt_time(c.start)}] [{c.language.upper()} · {c.source}] {c.text}" for c in items)
        path.write_text(content, encoding="utf-8-sig" if path.suffix.lower() != ".json" else "utf-8")


def srt_time(seconds):
    ms = max(0, round(seconds * 1000))
    sec, ms = divmod(ms, 1000)
    minutes, sec = divmod(sec, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{sec:02},{ms:03}"
