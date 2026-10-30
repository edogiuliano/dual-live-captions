import importlib.metadata
import platform
import subprocess
import sys
import psutil
from .runtime import configure_dlls
from . import __version__


def report():
    result = {"version": __version__, "os": platform.platform(), "python": sys.version.split()[0], "ram_process_mb": round(psutil.Process().memory_info().rss / 1048576, 1), "cuda_dll_directories": configure_dlls()}
    result["packages"] = {}
    for name in ("faster-whisper", "ctranslate2", "PySide6-Essentials", "onnxruntime", "PyAudioWPatch", "soxr"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = "bundled / no metadata"
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result["nvidia_smi"] = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader"], text=True, timeout=4, creationflags=flags).strip()
    except Exception:
        result["nvidia_smi"] = "No disponible"
    return result
