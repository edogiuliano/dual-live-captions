"""Bounded, in-memory comparison of text actually exposed by caption windows.

Windows is a comparison baseline, never assumed to be a ground-truth transcript.
Only numeric summaries leave this module; caption words remain in RAM.
"""
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from fractions import Fraction
import re
import statistics
import unicodedata


def tokenize(text):
    return re.findall(r"\w+(?:'\w+)*", unicodedata.normalize("NFC", text).casefold().replace("’", "'"))


@dataclass
class Occurrence:
    id: int
    word: str
    first: float
    ignored: bool = False
    retired: bool = False
    position: Fraction | None = None


class SnapshotTracker:
    def __init__(self, retention=180, capacity=5000):
        self.retention = retention
        self.capacity = capacity
        self.ledger = deque(maxlen=capacity)
        self.current = None
        self.serial = 0
        self.revisions = 0
        self.changes = 0
        self.last_change = None
        self.observed_words = 0
        self.max_position = Fraction(0)

    def _new(self, word, now, ignored=False):
        self.serial += 1
        node = Occurrence(self.serial, word, now, ignored)
        if not ignored:
            self.ledger.append(node)
            self.observed_words += 1
        return node

    def update(self, text, now):
        words = tokenize(text)[-800:]
        if self.current is None:
            # Exclude all text already present when measurement starts. It may
            # contain a previous conversation and has no valid appearance time.
            self.current = [self._new(w, now, True) for w in words]
            for i, node in enumerate(self.current, 1):
                node.position = Fraction(i)
            self.max_position = Fraction(len(words))
            return False
        old_words = [n.word for n in self.current]
        if words == old_words:
            self.prune(now)
            return False
        matcher = SequenceMatcher(None, old_words, words, autojunk=False)
        updated = []
        for kind, i, end_i, j, end_j in matcher.get_opcodes():
            if kind == "equal":
                updated.extend(self.current[i:end_i])
                continue
            # A rolling caption window drops its prefix: this is NOT a correction.
            scroll_off = kind == "delete" and i == 0 and j == 0 and end_i < len(old_words)
            if kind in ("replace", "delete") and not scroll_off:
                changed = [n for n in self.current[i:end_i] if not n.ignored and not n.retired]
                self.revisions += len(changed)
                for node in changed:
                    node.retired = True
            if kind in ("replace", "insert"):
                updated.extend(self._new(w, now) for w in words[j:end_j])
        # Revisions get a NEW appearance time, but retain their place in the
        # spoken sequence. Appending revised words to the end corrupts alignment.
        index = 0
        while index < len(updated):
            if updated[index].position is not None:
                index += 1
                continue
            end = index
            while end < len(updated) and updated[end].position is None:
                end += 1
            count = end - index
            upper = updated[end].position if end < len(updated) else None
            lower = updated[index - 1].position if index else None
            if lower is None:
                lower = upper - count - 1 if upper is not None else self.max_position
            if upper is None:
                upper = lower + count + 1
            for offset in range(count):
                updated[index + offset].position = lower + (upper - lower) * Fraction(offset + 1, count + 1)
                self.max_position = max(self.max_position, updated[index + offset].position)
            index = end
        self.current = updated
        self.changes += 1
        self.last_change = now
        self.prune(now)
        return True

    def prune(self, now):
        while self.ledger and self.ledger[0].first < now - self.retention:
            self.ledger.popleft()

    def stable(self, now, age=1.0, limit=300):
        self.prune(now)
        return sorted((n for n in self.ledger if not n.retired and not n.ignored and now - n.first >= age), key=lambda n: n.position)[-limit:]


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


class LiveComparison:
    def __init__(self, language="en"):
        self.language = language
        self.windows = SnapshotTracker()
        self.dual = {lang: SnapshotTracker() for lang in ("en", "es")}
        self.resets = 0

    def reset(self):
        language, resets = self.language, self.resets
        self.__init__(language)
        self.resets = resets + 1

    def observe(self, windows_text, dual_texts, windows_time, dual_time):
        self.windows.update(windows_text, windows_time)
        for lang in ("en", "es"):
            self.dual[lang].update(dual_texts.get(lang, ""), dual_time)

    def summarize(self, now):
        left = self.windows.stable(now)
        right = self.dual[self.language].stable(now)
        matcher = SequenceMatcher(None, [n.word for n in left], [n.word for n in right], autojunk=False)
        blocks = []
        for block in matcher.get_matching_blocks():
            if block.size < 3:
                continue
            deltas = [right[block.b + i].first - left[block.a + i].first for i in range(block.size)]
            # Context and plausible time correspondence disambiguate repeated
            # function words. Widely separated repetitions cannot establish lag.
            if max(abs(d) for d in deltas) > 12 or max(deltas) - min(deltas) > 4:
                continue
            blocks.append(block)
        deltas = [right[b.b + i].first - left[b.a + i].first for b in blocks for i in range(b.size)]
        agreement, compared, edits = None, 0, None
        if blocks:
            first, last = blocks[0], blocks[-1]
            a = [n.word for n in left[first.a:last.a + last.size]]
            b = [n.word for n in right[first.b:last.b + last.size]]
            compared = max(len(a), len(b))
            if compared >= 8:
                edits = edit_distance(a, b)
                agreement = max(0.0, 100 * (1 - edits / compared))
        last = max((t.last_change for t in [self.windows, *self.dual.values()] if t.last_change is not None), default=None)
        return {
            "language": self.language,
            "matched_words": len(deltas),
            "compared_words": compared,
            "edit_operations_vs_windows": edits,
            "word_agreement_percent": agreement,
            "dual_minus_windows_median_ms": statistics.median(deltas) * 1000 if deltas else None,
            "dual_minus_windows_p10_ms": percentile(deltas, .1) * 1000 if deltas else None,
            "dual_minus_windows_p90_ms": percentile(deltas, .9) * 1000 if deltas else None,
            "dual_first_percent": 100 * sum(d < -.15 for d in deltas) / len(deltas) if deltas else None,
            "windows_revised_words": self.windows.revisions,
            "dual_revised_words": self.dual[self.language].revisions,
            "windows_observed_words": self.windows.observed_words,
            "dual_en_observed_words": self.dual["en"].observed_words,
            "dual_es_observed_words": self.dual["es"].observed_words,
            "seconds_since_text_change": max(0, now - last) if last is not None else None,
            "baseline_resets": self.resets,
        }
