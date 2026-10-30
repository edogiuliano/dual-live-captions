from pathlib import Path
import json
import logging
import logging.handlers
import os
import sys
from .settings import data_dir

_dll_handles = []


def configure_dlls():
    if sys.platform != "win32":
        return []
    paths = [Path(sys.executable).parent / "gpu", data_dir() / "gpu"]
    if getattr(sys, "frozen", False):
        paths.append(Path(sys._MEIPASS) / "gpu")
    for key in ("DLC_CUDA_PATH", "CUDA_PATH"):
        if os.environ.get(key):
            paths += [Path(os.environ[key]), Path(os.environ[key]) / "bin"]
    try:
        paths += [Path(p) for p in json.loads((data_dir() / "gpu-paths.json").read_text(encoding="utf-8-sig"))]
    except (OSError, ValueError, TypeError):
        pass
    for path in sys.path:
        paths.append(Path(path) / "torch" / "lib")
    found = []
    for path in dict.fromkeys(paths):
        if path.is_dir() and (path / "cublas64_12.dll").exists() and (path / "cudnn64_9.dll").exists():
            _dll_handles.append(os.add_dll_directory(str(path)))
            os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
            found.append(str(path))
    return found


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    handler = logging.handlers.RotatingFileHandler(data_dir() / "diagnostics.log", maxBytes=512000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    # No exception strings from ASR/network libraries; they may contain input.
    for name in ("httpx", "httpx2", "huggingface_hub", "faster_whisper", "ctranslate2"):
        logger = logging.getLogger(name)
        logger.disabled = True
