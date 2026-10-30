import re
from lingua import Language, LanguageDetectorBuilder


class LanguageRouter:
    """Local text evidence complements acoustic language, never translates text."""
    def __init__(self):
        self.detector = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SPANISH).build()

    def classify(self, text, acoustic=None, acoustic_confidence=0.0):
        clean = re.sub(r"[^\wáéíóúüñ ]", " ", text).strip()
        if not clean:
            return None
        values = self.detector.compute_language_confidence_values(clean)
        best = values[0]
        code = "en" if best.language == Language.ENGLISH else "es"
        if len(clean.split()) < 3 and acoustic in ("en", "es") and acoustic_confidence >= .7:
            return acoustic
        # Single words/names are often ambiguous; use acoustic evidence only when strong.
        if len(clean.split()) < 3 and best.value < 0.88:
            return acoustic if acoustic in ("en", "es") and acoustic_confidence >= .55 else None
        if best.value >= .72:
            return code
        return acoustic if acoustic in ("en", "es") and acoustic_confidence >= .55 else None

    def route(self, words, acoustic, confidence):
        if not words:
            return []
        text = "".join(w.text for w in words)
        whole = self.classify(text, acoustic, confidence)
        # Sentence boundaries give substantially stronger evidence than isolated words.
        groups, current = [], []
        for word in words:
            current.append(word)
            if re.search(r"[.!?;:]$", word.text.strip()):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        result = []
        for group in groups:
            phrase = "".join(w.text for w in group)
            lang = self.classify(phrase, acoustic, confidence) or whole
            # Lingua spans support code switches within a longer sentence, requiring
            # at least three words per side to avoid routing English names as Spanish.
            spans = self.detector.detect_multiple_languages_of(phrase) if len(group) >= 7 else []
            if len(spans) > 1 and all(s.word_count >= 3 for s in spans):
                offset = 0
                buckets = []
                for word in group:
                    center = offset + len(word.text) // 2
                    span = next((s for s in spans if s.start_index <= center < s.end_index), spans[-1])
                    code = "en" if span.language == Language.ENGLISH else "es"
                    if buckets and buckets[-1][0] == code:
                        buckets[-1][1].append(word)
                    else:
                        buckets.append((code, [word]))
                    offset += len(word.text)
                result.extend(buckets)
            elif lang:
                result.append((lang, group))
        return result
