"""Reproducible synthetic corpus benchmark. Never records user conversations."""
import argparse
from datetime import date
from dataclasses import asdict
import json
from pathlib import Path
import queue
import re
import statistics
import subprocess
import threading
import time
import unicodedata
import numpy as np
import psutil
from faster_whisper.audio import decode_audio
from dual_live_captions.asr import FasterWhisperEngine
from dual_live_captions.models import cached_model
from dual_live_captions.settings import Settings
from dual_live_captions.audio import AudioFrame, BoundedAudioQueue
from dual_live_captions.pipeline import CaptionPipeline
from dual_live_captions.language import LanguageRouter

ROOT = Path(__file__).resolve().parents[2]
(ROOT / "artifacts").mkdir(exist_ok=True)


def tokens(text):
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def wer(reference, hypothesis):
    a, b = tokens(reference), tokens(hypothesis)
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = new
    return row[-1] / max(1, len(a))


def corpus():
    cases = json.loads((ROOT / "tests/audio_samples/reference.json").read_text(encoding="utf-8-sig"))
    for case in cases:
        case["audio"] = decode_audio(str(ROOT / "tests/audio_samples" / (case["id"] + ".wav")), sampling_rate=16000)
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["base", "small"])
    parser.add_argument("--device", default="auto")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    cases = corpus()
    router = LanguageRouter()
    report = {"corpus": "Windows SAPI synthetic speech, six fixtures, NOT human or YouTube accuracy", "date": date.today().isoformat(), "models": {}}
    stop = threading.Event()
    resources = []
    def monitor():
        while not stop.is_set():
            try:
                gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=3)
                memory, usage = [float(x.strip()) for x in gpu.strip().split(",")]
                resources.append({"time": time.monotonic(), "gpu_total_mb": memory, "gpu_utilization": usage, "rss_mb": psutil.Process().memory_info().rss / 1048576})
            except Exception:
                pass
            stop.wait(.5)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        for model in args.models:
            path = cached_model(model)
            if not path:
                report["models"][model] = {"error": "model not cached"}
                continue
            config = Settings(model=model, device=args.device)
            engine = FasterWhisperEngine(path, config, print)
            rows = []
            for case in cases:
                result = engine.transcribe(case["audio"])
                text = "".join(w.text for w in result.words).strip()
                routed = router.route(result.words, result.language, result.confidence)
                rows.append({"id": case["id"], "expected_language": case["language"], "acoustic_language": result.language, "routed_languages": [l for l, _ in routed], "reference": case["text"], "text": text, "wer": wer(case["text"], text), "audio_seconds": len(case["audio"]) / 16000, "inference_ms": result.inference_ms})
                print(json.dumps(rows[-1], ensure_ascii=True), flush=True)
            silent = engine.transcribe(np.zeros(16000 * 3, np.float32))
            data = {"device": engine.device, "fixtures": rows, "silence_words_raw_asr": len(silent.words), "macro_wer": statistics.mean(r["wer"] for r in rows)}
            if args.stream and model == args.models[-1]:
                blocks, refs, cursor = [np.zeros(8000, np.float32)], [], .5
                for index in (0, 1, 2, 3, 4, 5, 2, 3):
                    case = cases[index]
                    refs.append({"id": case["id"], "start": cursor, "end": cursor + len(case["audio"]) / 16000, "language": case["language"], "text": case["text"]})
                    blocks += [case["audio"], np.zeros(8000 if index < 4 else 2400, np.float32)]
                    cursor += len(case["audio"]) / 16000 + (0.5 if index < 4 else .15)
                blocks.append(np.zeros(16000 * 4, np.float32))
                audio = np.concatenate(blocks)
                np.save(ROOT / "artifacts/bilingual-fixture.npy", audio)
                import wave
                with wave.open(str(ROOT / "artifacts/bilingual-fixture.wav"), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
                events, metrics = [], []
                epoch = time.monotonic()
                pipe = CaptionPipeline(engine, config, lambda c: events.append(dict(asdict(c), elapsed=time.monotonic() - epoch)), metrics.append)
                incoming = BoundedAudioQueue()
                ended = threading.Event()
                def produce():
                    for pos in range(0, len(audio) - 511, 512):
                        target = epoch + (pos + 512) / 16000
                        time.sleep(max(0, target - time.monotonic()))
                        incoming.put(AudioFrame("fixture", audio[pos:pos + 512], pos / 16000, time.monotonic()))
                    ended.set()
                producer = threading.Thread(target=produce, daemon=True)
                producer.start()
                while not ended.is_set() or not incoming.queue.empty():
                    try:
                        pipe.feed(incoming.queue.get(timeout=.1))
                    except queue.Empty:
                        pass
                pipe.flush()
                data["stream"] = {"duration": len(audio) / 16000, "references": refs, "events": events, "metrics": metrics, "dropped_frames": incoming.dropped}
                for lang in ("en", "es"):
                    expected = " ".join(r["text"] for r in refs if r["language"] == lang)
                    got = " ".join(e["text"] for e in events if e["final"] and e["language"] == lang)
                    data["stream"][f"{lang}_wer"] = wer(expected, got)
                    data["stream"][f"{lang}_text"] = got
                firsts = []
                for ref in refs:
                    candidates = [e for e in events if e["text"] and e["language"] == ref["language"] and ref["start"] - .3 <= e["start"] <= ref["end"]]
                    if candidates:
                        firsts.append(min(e["elapsed"] for e in candidates) - ref["start"])
                data["stream"]["first_text_latencies_seconds"] = firsts
                print("STREAM", {k: v for k, v in data["stream"].items() if k not in ("events", "metrics", "references")}, flush=True)
            report["models"][model] = data
            del engine
    finally:
        stop.set()
        thread.join(timeout=4)
        report["resources"] = resources
        (ROOT / "artifacts/benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
