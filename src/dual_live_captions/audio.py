from dataclasses import dataclass
import logging
import queue
import threading
import time
from contextlib import contextmanager
import numpy as np
import soxr

SAMPLE_RATE = 16000
FRAME = 512
log = logging.getLogger(__name__)
_portaudio_lock = threading.RLock()


@contextmanager
def portaudio_context(pa):
    # PortAudio initialization/termination and device enumeration are not safe
    # to race between independent capture threads.
    with _portaudio_lock:
        instance = pa.PyAudio()
    try:
        yield instance
    finally:
        with _portaudio_lock:
            instance.terminate()


@dataclass
class AudioFrame:
    source: str
    samples: np.ndarray
    start: float
    captured: float
    discontinuity: bool = False


class BoundedAudioQueue:
    def __init__(self, size=96):
        self.queue = queue.Queue(maxsize=size)
        self.dropped = 0

    def put(self, item):
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            self.dropped += 1
            item.discontinuity = True
            try:
                self.queue.put_nowait(item)
            except queue.Full:
                self.dropped += 1

    def clear(self):
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break


class RingBuffer:
    def __init__(self, capacity):
        self.data = np.zeros(capacity, dtype=np.float32)
        self.capacity = capacity
        self.total = 0
        self.size = 0

    def append(self, values):
        values = np.asarray(values, dtype=np.float32)
        if len(values) >= self.capacity:
            self.data[:] = values[-self.capacity:]
            self.total += len(values)
            self.size = self.capacity
            self._position = 0
            return
        pos = getattr(self, "_position", 0)
        count = min(len(values), self.capacity - pos)
        self.data[pos:pos + count] = values[:count]
        self.data[:len(values) - count] = values[count:]
        self._position = (pos + len(values)) % self.capacity
        self.total += len(values)
        self.size = min(self.capacity, self.size + len(values))

    def read(self):
        pos = getattr(self, "_position", 0)
        if self.size < self.capacity:
            return self.data[:self.size].copy()
        return np.concatenate((self.data[pos:], self.data[:pos]))


class Converter:
    def __init__(self, rate, channels):
        self.channels = channels
        self.resampler = soxr.ResampleStream(rate, SAMPLE_RATE, 1, dtype="float32", quality="HQ")
        self.pending = np.empty(0, dtype=np.float32)

    def convert(self, raw):
        x = np.frombuffer(raw, dtype=np.float32).reshape(-1, self.channels).mean(axis=1)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        x = self.resampler.resample_chunk(np.clip(x, -1, 1))
        self.pending = np.concatenate((self.pending, x))
        result = []
        while len(self.pending) >= FRAME:
            result.append(self.pending[:FRAME].copy())
            self.pending = self.pending[FRAME:]
        return result


def enumerate_devices():
    import pyaudiowpatch as pa
    with portaudio_context(pa) as p:
        host = p.get_host_api_info_by_type(pa.paWASAPI)["index"]
        outputs = [{"name": d["name"], "id": d["name"]} for d in p.get_loopback_device_info_generator()]
        inputs = [{"name": d["name"], "id": d["name"]} for d in (p.get_device_info_by_index(i) for i in range(p.get_device_count())) if d["hostApi"] == host and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice")]
        return outputs, inputs


class WasapiCapture(threading.Thread):
    def __init__(self, source, device_name, target, stop, paused, epoch, status):
        super().__init__(name=f"capture-{source}", daemon=True)
        self.source, self.device_name, self.target = source, device_name, target
        self.stop_event, self.paused, self.epoch, self.status = stop, paused, epoch, status

    def resolve(self, p, pa):
        snapshot = getattr(self, "native_snapshot", None)
        native_name = None
        if snapshot:
            if self.device_name == "default" and snapshot.get(self.source):
                native_name = snapshot[self.source][1]
            elif self.device_name != "default":
                chosen_name = self.device_name.removesuffix(" [Loopback]")
                if chosen_name not in {name for _, name in snapshot["active"]}:
                    raise OSError("Dispositivo desconectado")
        if self.source == "system":
            if self.device_name == "default" and native_name is None:
                return p.get_default_wasapi_loopback()
            devices = list(p.get_loopback_device_info_generator())
        else:
            if self.device_name == "default" and native_name is None:
                return p.get_device_info_by_index(p.get_host_api_info_by_type(pa.paWASAPI)["defaultInputDevice"])
            host = p.get_host_api_info_by_type(pa.paWASAPI)["index"]
            devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
            devices = [d for d in devices if d["hostApi"] == host and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice")]
        wanted = native_name + (" [Loopback]" if self.source == "system" else "") if native_name else self.device_name
        found = next((d for d in devices if d["name"] == wanted), None)
        if found is None:
            raise OSError("Dispositivo desconectado")
        return found

    def run(self):
        import comtypes
        comtypes.CoInitialize()
        try:
            self._capture_loop()
        finally:
            comtypes.CoUninitialize()

    def _capture_loop(self):
        import pyaudiowpatch as pa
        while not self.stop_event.is_set():
            try:
                from .windows_devices import endpoint_snapshot
                self.native_snapshot = endpoint_snapshot()
                with portaudio_context(pa) as p:
                    d = self.resolve(p, pa)
                    channels, rate = min(2, d["maxInputChannels"]), int(d["defaultSampleRate"])
                    converter = Converter(rate, channels)
                    packets = queue.Queue(maxsize=32)
                    packet_dropped = threading.Event()
                    def callback(raw, frame_count, time_info, flags):
                        if self.stop_event.is_set():
                            return None, pa.paComplete
                        if not self.paused.is_set():
                            try:
                                packets.put_nowait((raw, time.monotonic()))
                            except queue.Full:
                                packet_dropped.set()
                        return None, pa.paContinue
                    with _portaudio_lock:
                        stream = p.open(format=pa.paFloat32, channels=channels, rate=rate, input=True, input_device_index=d["index"], frames_per_buffer=int(rate * .032), stream_callback=callback)
                    self.status(f"audio:{self.source}:conectado")
                    next_check = time.monotonic() + 2
                    next_start = None
                    try:
                        while not self.stop_event.is_set():
                            now = time.monotonic()
                            # Timeout keeps shutdown/hotplug responsive even when a
                            # silent endpoint supplies no loopback packets at all.
                            try:
                                raw, captured = packets.get(timeout=.1)
                            except queue.Empty:
                                raw, captured = None, now
                            if self.paused.is_set():
                                next_start = None
                                continue
                            if raw is not None:
                                frames = converter.convert(raw)
                                gap = packet_dropped.is_set() or (next_start is not None and abs(captured - self.epoch - next_start) > .3)
                                if next_start is None or gap:
                                    next_start = max(0, captured - self.epoch - len(frames) * FRAME / SAMPLE_RATE)
                                packet_dropped.clear()
                                for index, frame in enumerate(frames):
                                    self.target.put(AudioFrame(self.source, frame, next_start, captured, gap and index == 0))
                                    next_start += FRAME / SAMPLE_RATE
                            # Recreate PortAudio's device snapshot to notice hotplug/default changes.
                            if now >= next_check:
                                native_now = endpoint_snapshot()
                                if native_now != self.native_snapshot:
                                    self.status(f"audio:{self.source}:actualizando dispositivos")
                                    break
                                with portaudio_context(pa) as fresh:
                                    current = self.resolve(fresh, pa)
                                if current["name"] != d["name"] or current["defaultSampleRate"] != d["defaultSampleRate"]:
                                    self.status(f"audio:{self.source}:cambiando salida")
                                    break
                                next_check = now + 2
                    finally:
                        with _portaudio_lock:
                            stream.stop_stream()
                            stream.close()
                        # Release native resampler before Python interpreter exit.
                        converter.resampler = None
                self.stop_event.wait(.5)
            except Exception as exc:
                code = getattr(exc, "errno", None)
                log.warning("capture_reconnect source=%s error=%s code=%s", self.source, type(exc).__name__, code)
                self.status(f"audio:{self.source}:reconectando ({type(exc).__name__}, código {code})")
                self.stop_event.wait(1.0)
