from dataclasses import dataclass
from typing import Protocol
import time
import numpy as np
from .runtime import configure_dlls
from .subtitles import Word


@dataclass
class Recognition:
    words: list
    language: str
    confidence: float
    inference_ms: float


class ASREngine(Protocol):
    def transcribe(self, audio: np.ndarray) -> Recognition: ...


class FasterWhisperEngine:
    def __init__(self, model_path, settings, status=lambda _: None):
        dlls = configure_dlls()
        import ctranslate2
        from faster_whisper import WhisperModel
        can_cuda = ctranslate2.get_cuda_device_count() > 0
        # Explicit CUDA is attempted and reported; auto requires known runtime DLLs.
        self.device = "cuda" if settings.device == "cuda" or (settings.device == "auto" and can_cuda and dlls) else "cpu"
        compute = settings.compute_type if self.device == "cuda" else "int8"
        self.beam = settings.beam_size
        status(f"Cargando modelo · {self.device.upper()} / {compute}")
        self.model = WhisperModel(model_path, device=self.device, compute_type=compute, cpu_threads=4, num_workers=1, local_files_only=True)
        # Real inference loads cuDNN as well. Silence here is never published.
        list(self.model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1, max_new_tokens=4, task="transcribe")[0])
        status(f"Listo · {self.device.upper()} / {compute}")

    def transcribe(self, audio):
        started = time.perf_counter()
        segments, info = self.model.transcribe(
            audio, task="transcribe", language=None, beam_size=self.beam,
            temperature=0.0, condition_on_previous_text=False,
            word_timestamps=True, vad_filter=False, without_timestamps=False,
            no_speech_threshold=.6, log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4, max_new_tokens=112,
            hallucination_silence_threshold=1.0,
        )
        words = []
        for segment in segments:
            if segment.avg_logprob < -1.0 or segment.no_speech_prob > .65 or segment.compression_ratio > 2.6:
                continue
            for word in segment.words or []:
                if word.probability >= .18 and word.end > word.start:
                    words.append(Word(word.word, word.start, word.end, word.probability))
        return Recognition(words, info.language, info.language_probability, (time.perf_counter() - started) * 1000)


class SileroStreamingVAD:
    def __init__(self):
        from faster_whisper.vad import get_vad_model
        self.session = get_vad_model().session
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), np.float32)
        self.c = np.zeros((1, 1, 128), np.float32)
        self.context = np.zeros((1, 64), np.float32)

    def probability(self, audio):
        if len(audio) != 512:
            raise ValueError("VAD requiere bloques de 512 muestras a 16 kHz")
        x = np.concatenate((self.context, audio.reshape(1, -1)), axis=1)
        output, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
        self.context = audio[-64:].reshape(1, -1).copy()
        return float(np.asarray(output).reshape(-1)[0])
