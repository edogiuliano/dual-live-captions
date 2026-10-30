import logging
import queue
import time
from dataclasses import replace
from .audio import BoundedAudioQueue, WasapiCapture
from .runtime import setup_logging
from .asr import FasterWhisperEngine
from .pipeline import CaptionPipeline


def run_service(settings, model_path, output, stop, paused, session_epoch=None):
    """Capture + ASR isolated from GUI, including fatal native CUDA failures."""
    setup_logging()
    def send(kind, value):
        try:
            output.put((kind, value), timeout=.2)
        except queue.Full:
            # UI receives a visible discontinuity instead of unbounded IPC memory.
            if kind == "caption":
                stop.set()
    status = lambda text: send("status", text)
    captures = []
    audio = BoundedAudioQueue()
    epoch = time.monotonic()
    try:
        try:
            engine = FasterWhisperEngine(model_path, settings, status)
        except Exception as exc:
            if settings.device == "cpu":
                raise
            status(f"GPU no disponible ({type(exc).__name__}); usando CPU")
            settings = replace(settings, device="cpu")
            engine = FasterWhisperEngine(model_path, settings, status)
        send("engine", engine.device)
        pipeline = CaptionPipeline(engine, settings, lambda c: send("caption", c), lambda m: send("metrics", m), lambda busy: send("busy", busy))
        epoch = session_epoch if session_epoch is not None else time.monotonic()
        send("epoch", epoch)
        if settings.system_audio:
            captures.append(WasapiCapture("system", settings.output, audio, stop, paused, epoch, status))
        if settings.microphone != "none":
            captures.append(WasapiCapture("microphone", settings.microphone, audio, stop, paused, epoch, status))
        for capture in captures:
            capture.start()
        status("Capturando")
        last_metrics = 0.0
        was_paused = False
        dropped = 0
        while not stop.is_set():
            if paused.is_set():
                if not was_paused:
                    pipeline.reset()
                    audio.clear()
                    status("En pausa")
                    was_paused = True
                stop.wait(.05)
                continue
            if was_paused:
                audio.clear()
                status("Capturando")
                was_paused = False
            try:
                frame = audio.queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                pipeline.feed(frame)
            except Exception as exc:
                logging.getLogger(__name__).warning("inference_recovery error=%s", type(exc).__name__)
                if engine.device == "cuda":
                    status("Error GPU; recuperando en CPU")
                    settings = replace(settings, device="cpu")
                    engine = FasterWhisperEngine(model_path, settings, status)
                    send("engine", engine.device)
                    pipeline = CaptionPipeline(engine, settings, lambda c: send("caption", c), lambda m: send("metrics", m), lambda busy: send("busy", busy))
                    audio.clear()
                else:
                    raise
            now = time.monotonic()
            if now - last_metrics > .1:
                import numpy as np
                send("level", min(1.0, float(np.sqrt(np.mean(frame.samples ** 2))) * 8))
                last_metrics = now
            if audio.dropped != dropped:
                dropped = audio.dropped
                status(f"Sobrecarga: {dropped} bloques descartados; reducí calidad")
                send("dropped", dropped)
        # Stop is immediate and discards unconfirmed tail; pause never transcribes
        # audio collected while paused. Confirmed captions remain in the GUI.
        pipeline.reset()
    except Exception as exc:
        logging.getLogger(__name__).error("service_failed error=%s", type(exc).__name__)
        send("error", f"No se pudo iniciar o continuar ({type(exc).__name__}). Revisá Diagnóstico.")
    finally:
        stop.set()
        for capture in captures:
            capture.join(timeout=2)
        send("stopped", None)
