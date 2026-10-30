"""Open simultaneous sources; retain counters only."""
import json
from pathlib import Path
import queue
import threading
import time
import argparse
from dual_live_captions.audio import WasapiCapture, BoundedAudioQueue, portaudio_context
import pyaudiowpatch as pa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--microphone", default="default")
    parser.add_argument("--play-fixture", action="store_true")
    options = parser.parse_args()
    incoming = BoundedAudioQueue()
    stop, paused = threading.Event(), threading.Event()
    epoch = time.monotonic()
    status = []
    with portaudio_context(pa) as backend:
        selected = backend.get_default_wasapi_loopback()["name"]
    microphone = options.microphone
    if microphone != "default":
        from dual_live_captions.audio import enumerate_devices
        microphone = next(d["id"] for d in enumerate_devices()[1] if microphone in d["name"])
    workers = [WasapiCapture("system", selected, incoming, stop, paused, epoch, status.append), WasapiCapture("microphone", microphone, incoming, stop, paused, epoch, status.append)]
    for worker in workers:
        worker.start()
    if options.play_fixture:
        import winsound
        fixture = Path(__file__).resolve().parents[2] / "tests/audio_samples/english.wav"
        winsound.PlaySound(str(fixture), winsound.SND_FILENAME | winsound.SND_ASYNC)
    counts = {"system": 0, "microphone": 0}
    end = time.monotonic() + 5
    while time.monotonic() < end:
        try:
            frame = incoming.queue.get(timeout=.1)
            counts[frame.source] += 1
        except queue.Empty:
            pass
    stop.set()
    if options.play_fixture:
        winsound.PlaySound(None, winsound.SND_PURGE)
    for worker in workers:
        worker.join(timeout=3)
    result = {"frames": counts, "status": status, "threads_stopped": all(not w.is_alive() for w in workers), "selected_output": selected}
    path = Path(__file__).resolve().parents[2] / "artifacts/sources-probe.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
