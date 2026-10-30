from collections import deque
from dataclasses import replace
import time
import numpy as np
from .audio import SAMPLE_RATE, FRAME, RingBuffer
from .asr import SileroStreamingVAD
from .language import LanguageRouter
from .subtitles import Agreement, Caption


class StreamState:
    def __init__(self, settings):
        self.vad = SileroStreamingVAD()
        self.pre_roll = deque(maxlen=8)
        self.audio = RingBuffer(int(settings.max_window * SAMPLE_RATE))
        self.active = False
        self.origin = 0.0
        self.last_voice = 0.0
        self.last_decode = 0.0
        self.agreement = Agreement()
        self.number = 0
        self.latest_captured = 0.0
        self.expected = None

    def reset_utterance(self):
        self.audio = RingBuffer(self.audio.capacity)
        self.active = False
        self.agreement = Agreement()
        self.pre_roll.clear()
        self.number += 1


class CaptionPipeline:
    def __init__(self, engine, settings, emit, metrics=lambda _: None, activity=lambda _: None):
        self.engine, self.settings, self.emit, self.metrics = engine, settings, emit, metrics
        self.router = LanguageRouter()
        self.states = {}
        self.serial = 0
        self.activity = activity

    def feed(self, frame):
        state = self.states.setdefault(frame.source, StreamState(self.settings)) if frame.source not in self.states else self.states[frame.source]
        if frame.discontinuity or (state.expected is not None and abs(frame.start - state.expected) > .15):
            self.clear_partial(frame.source, state)
            state.reset_utterance()
            state.vad.reset()
        state.expected = frame.start + len(frame.samples) / SAMPLE_RATE
        state.latest_captured = frame.captured
        probability = state.vad.probability(frame.samples)
        rms = float(np.sqrt(np.mean(frame.samples ** 2)))
        voice = probability >= self.settings.vad_threshold and rms >= .001
        end = frame.start + FRAME / SAMPLE_RATE
        if not state.active:
            state.pre_roll.append(frame.samples)
            if not voice:
                return
            state.active = True
            state.origin = frame.start - (len(state.pre_roll) - 1) * FRAME / SAMPLE_RATE
            state.last_decode = state.origin
            for block in state.pre_roll:
                state.audio.append(block)
            state.pre_roll.clear()
        else:
            state.audio.append(frame.samples)
        if voice:
            state.last_voice = end
        if end - state.last_voice >= self.settings.silence:
            self.decode(frame.source, state, final=True)
            state.reset_utterance()
        elif end - state.origin >= self.settings.min_speech and end - state.last_decode >= self.settings.interval:
            self.decode(frame.source, state)
            state.last_decode = end

    def decode(self, source, state, final=False):
        audio = state.audio.read()
        if len(audio) < SAMPLE_RATE * .32:
            self.clear_partial(source, state)
            return
        buffer_origin = state.origin + max(0, state.audio.total - state.audio.size) / SAMPLE_RATE
        # Confirmed prefix is kept as audio context until bounded buffer rolls forward.
        self.activity(True)
        try:
            result = self.engine.transcribe(audio)
        finally:
            self.activity(False)
        words = [replace(w, start=w.start + buffer_origin, end=w.end + buffer_origin) for w in result.words]
        committed, partial = state.agreement.update(words, final, buffer_origin + len(audio) / SAMPLE_RATE)
        self.clear_partial(source, state)
        for language, group in self.router.route(committed, result.language, result.confidence):
            if language not in self.settings.languages:
                continue
            self.serial += 1
            self.emit(Caption(f"{source}-{self.serial}", source, language, "".join(w.text for w in group).strip(), group[0].start, group[-1].end, True, time.monotonic()))
        if not final:
            for language, group in self.router.route(partial, result.language, result.confidence):
                if language in self.settings.languages:
                    self.emit(Caption(f"partial-{source}-{language}", source, language, "".join(w.text for w in group).strip(), group[0].start, group[-1].end, False, time.monotonic()))
        self.metrics({"inference_ms": result.inference_ms, "capture_to_publish_ms": max(0, (time.monotonic() - state.latest_captured) * 1000), "buffer_seconds": len(audio) / SAMPLE_RATE, "source": source})

    def clear_partial(self, source, state):
        for lang in ("en", "es"):
            self.emit(Caption(f"partial-{source}-{lang}", source, lang, "", 0, 0, False, time.monotonic()))

    def flush(self):
        for source, state in self.states.items():
            if state.active:
                self.decode(source, state, final=True)
                state.reset_utterance()

    def reset(self):
        for source, state in self.states.items():
            self.clear_partial(source, state)
        self.states.clear()
