import io
import json
import threading
import pytest
from dual_live_captions import models, service
from dual_live_captions.settings import Settings
from dual_live_captions.audio import WasapiCapture, BoundedAudioQueue


def test_initial_gpu_failure_falls_back_to_cpu_and_stops(monkeypatch):
    settings = Settings(system_audio=False, microphone="none")
    devices, events = [], []
    stop, paused = threading.Event(), threading.Event()
    class Output:
        def put(self, value, timeout=None):
            events.append(value)
            if value == ("status", "Capturando"):
                stop.set()
    class Engine:
        def __init__(self, path, config, status):
            devices.append(config.device)
            if config.device != "cpu":
                raise RuntimeError("injected GPU initialization failure")
            self.device = "cpu"
    monkeypatch.setattr(service, "FasterWhisperEngine", Engine)
    service.run_service(settings, "unused", Output(), stop, paused)
    assert devices == ["auto", "cpu"]
    assert ("engine", "cpu") in events
    assert events[-1] == ("stopped", None)
    assert not [e for e in events if e[0] == "caption" and e[1].text]


def test_corrupt_model_never_gets_verified_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "data_dir", lambda: tmp_path)
    metadata = {"sha": "revision", "siblings": [{"rfilename": "model.bin", "size": 3, "lfs": {"size": 3, "sha256": "0" * 64}}]}
    class Response(io.BytesIO):
        status = 200
    def fetch(request, timeout):
        if "/api/models/" in request.full_url:
            return Response(json.dumps(metadata).encode())
        return Response(b"bad")
    monkeypatch.setattr(models.urllib.request, "urlopen", fetch)
    with pytest.raises(ValueError, match="integridad"):
        models.download("tiny", lambda *_: None, threading.Event())
    assert not (tmp_path / "models/tiny/verified.json").exists()
    assert not (tmp_path / "models/tiny/model.bin").exists()


def test_settings_disabled_history_is_saved_without_transcripts(tmp_path):
    path = tmp_path / "settings.json"
    Settings(history_enabled=False).save(path)
    raw = path.read_text(encoding="utf-8")
    assert json.loads(raw)["history_enabled"] is False
    assert "captions" not in json.loads(raw)


def test_default_output_follows_fresh_windows_identity():
    class Backend:
        def get_loopback_device_info_generator(self):
            return iter([{"name": "Old [Loopback]", "index": 1}, {"name": "New [Loopback]", "index": 2}])
    capture = WasapiCapture("system", "default", BoundedAudioQueue(), threading.Event(), threading.Event(), 0, lambda _: None)
    capture.native_snapshot = {"system": ("new-id", "New"), "active": (("new-id", "New"),)}
    assert capture.resolve(Backend(), object())["index"] == 2


def test_selected_unplugged_output_is_not_silently_replaced():
    capture = WasapiCapture("system", "Old [Loopback]", BoundedAudioQueue(), threading.Event(), threading.Event(), 0, lambda _: None)
    capture.native_snapshot = {"system": ("new-id", "New"), "active": (("new-id", "New"),)}
    with pytest.raises(OSError, match="desconectado"):
        capture.resolve(object(), object())
