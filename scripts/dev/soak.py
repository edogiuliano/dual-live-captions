"""15/30/60/480 minute real-time ASR soak on synthetic files (no sound playback)."""
import argparse
import json
from pathlib import Path
import queue
import threading
import time
import numpy as np
import psutil
from dual_live_captions.asr import FasterWhisperEngine
from dual_live_captions.audio import AudioFrame, BoundedAudioQueue
from dual_live_captions.models import cached_model
from dual_live_captions.pipeline import CaptionPipeline
from dual_live_captions.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=15)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    (root / "artifacts").mkdir(exist_ok=True)
    audio = np.load(root / "artifacts/bilingual-fixture.npy")
    config = Settings()
    engine = FasterWhisperEngine(cached_model(config.model), config, print)
    events = BoundedAudioQueue()
    report = {"kind": "realtime synthetic file ASR soak; excludes WASAPI, GPU total load and physical device changes", "requested_minutes": args.minutes, "samples": [], "captions": 0, "errors": 0}
    ended = threading.Event()
    epoch = time.monotonic()
    def produce():
        position = 0
        while position / 16000 < args.minutes * 60:
            offset = position % len(audio)
            block = audio[offset:offset + 512]
            if len(block) < 512:
                block = np.concatenate((block, audio[:512 - len(block)]))
            target = epoch + (position + 512) / 16000
            time.sleep(max(0, target - time.monotonic()))
            events.put(AudioFrame("fixture", block, position / 16000, time.monotonic()))
            position += 512
        ended.set()
    def caption(value):
        if value.final and value.text:
            report["captions"] += 1
    latest = {}
    pipeline = CaptionPipeline(engine, config, caption, latest.update)
    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    next_sample = 0
    try:
        while not ended.is_set() or not events.queue.empty():
            try:
                pipeline.feed(events.queue.get(timeout=.1))
            except queue.Empty:
                pass
            now = time.monotonic() - epoch
            if now >= next_sample:
                sample = {"elapsed_seconds": now, "rss_mb": psutil.Process().memory_info().rss / 1048576, "queue_frames": events.queue.qsize(), "dropped_frames": events.dropped, **latest}
                report["samples"].append(sample)
                (root / "artifacts/soak-progress.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(f"{now:.0f}s RSS={sample['rss_mb']:.0f}MB dropped={events.dropped}", flush=True)
                next_sample = now + 30
        pipeline.flush()
        report["completed"] = True
    except Exception as exc:
        report["errors"] += 1
        report["error_type"] = type(exc).__name__
        raise
    finally:
        report["actual_seconds"] = time.monotonic() - epoch
        report["dropped_frames"] = events.dropped
        (root / "artifacts/soak-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
