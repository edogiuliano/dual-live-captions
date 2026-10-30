"""Live browser audio probe. Records counters/metrics only, no audio or text."""
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import queue
import time
from dual_live_captions.models import cached_model
from dual_live_captions.service import run_service
from dual_live_captions.settings import Settings


def main():
    mp.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=180)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    (root / "artifacts").mkdir(exist_ok=True)
    control = root / "artifacts/probe-control.json"
    ctx = mp.get_context("spawn")
    events, stop, pause = ctx.Queue(256), ctx.Event(), ctx.Event()
    process = ctx.Process(target=run_service, args=(Settings(), cached_model("small"), events, stop, pause))
    process.start()
    start = time.monotonic()
    report = {"type": "real default WASAPI browser audio, no transcript or audio retained", "phases": {}, "errors": []}
    last_print = start
    try:
        while time.monotonic() - start < args.seconds and process.is_alive():
            try:
                phase = json.loads(control.read_text(encoding="utf-8"))["phase"]
            except Exception:
                phase = "unlabeled"
            record = report["phases"].setdefault(phase, {"confirmed_en": 0, "confirmed_es": 0, "partial_en": 0, "partial_es": 0, "metrics": [], "first_event_seconds": None, "last_event_seconds": None})
            try:
                kind, value = events.get(timeout=.1)
            except queue.Empty:
                continue
            if kind == "caption" and value.text:
                key = ("confirmed_" if value.final else "partial_") + value.language
                record[key] += 1
                elapsed = time.monotonic() - start
                if record["first_event_seconds"] is None:
                    record["first_event_seconds"] = elapsed
                record["last_event_seconds"] = elapsed
            elif kind == "metrics":
                record["metrics"].append(value)
            elif kind == "engine":
                report["engine"] = value
            elif kind == "error":
                report["errors"].append(value)
            now = time.monotonic()
            if now - last_print > 5:
                (root / "artifacts/browser-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(phase, {k: v for k, v in record.items() if k != "metrics"}, flush=True)
                last_print = now
    finally:
        stop.set()
        process.join(timeout=6)
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        report["seconds"] = time.monotonic() - start
        report["exitcode"] = process.exitcode
        (root / "artifacts/browser-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
