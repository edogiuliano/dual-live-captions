"""Inspect device formats only; does not retain audio."""
import pyaudiowpatch as pa
from dual_live_captions.windows_devices import endpoint_snapshot

print(endpoint_snapshot())
with pa.PyAudio() as backend:
    devices = [backend.get_device_info_by_index(i) for i in range(backend.get_device_count())]
    inputs = [d for d in devices if d["hostApi"] == backend.get_host_api_info_by_type(pa.paWASAPI)["index"] and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice")]
    for device in inputs:
        print(device["name"], device["maxInputChannels"], device["defaultSampleRate"])
        for fmt in (pa.paFloat32, pa.paInt16):
            try:
                stream = backend.open(format=fmt, channels=min(2, device["maxInputChannels"]), rate=int(device["defaultSampleRate"]), input=True, input_device_index=device["index"], frames_per_buffer=1536)
                print("opened format", fmt)
                stream.close()
            except Exception as exc:
                print(type(exc).__name__, str(exc))
