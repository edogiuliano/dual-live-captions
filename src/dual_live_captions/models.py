from pathlib import Path
import hashlib
import json
import urllib.request
from .settings import data_dir
from . import __version__

MODELS = {
    "tiny": ("Systran/faster-whisper-tiny", 80),
    "base": ("Systran/faster-whisper-base", 150),
    "small": ("Systran/faster-whisper-small", 500),
    "medium": ("Systran/faster-whisper-medium", 1550),
    "large-v3-turbo": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", 1650),
}
FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.json", "vocabulary.txt", "preprocessor_config.json")


def cached_model(name):
    if name not in MODELS:
        candidate = Path(name)
        return str(candidate) if (candidate / "model.bin").is_file() and (candidate / "config.json").is_file() else None
    own = data_dir() / "models" / name
    if (own / "verified.json").exists() and all((own / file).is_file() for file in ("model.bin", "config.json", "tokenizer.json")):
        return str(own)
    from huggingface_hub import snapshot_download
    try:
        path = snapshot_download(MODELS[name][0], local_files_only=True, allow_patterns=list(FILES))
        if all((Path(path) / f).exists() for f in ("model.bin", "config.json", "tokenizer.json")):
            return path
    except Exception:
        pass
    return None


def download(name, progress, cancelled):
    """Pinned snapshot, resumable files, SHA256 for HF LFS assets, atomic manifest."""
    if name not in MODELS:
        raise ValueError("Modelo desconocido")
    repo = MODELS[name][0]
    req = urllib.request.Request(f"https://huggingface.co/api/models/{repo}?blobs=true", headers={"User-Agent": f"DualLiveCaptions/{__version__}"})
    with urllib.request.urlopen(req, timeout=30) as response:
        info = json.load(response)
    revision = info["sha"]
    selected = [f for f in info["siblings"] if f["rfilename"] in FILES]
    total = sum(f.get("size", f.get("lfs", {}).get("size", 0)) for f in selected)
    root = data_dir() / "models" / name
    root.mkdir(parents=True, exist_ok=True)
    done = 0
    manifest = {"repo": repo, "revision": revision, "files": {}}
    for item in selected:
        filename = item["rfilename"]
        path = root / filename
        expected_hash = item.get("lfs", {}).get("sha256")
        size = item.get("size", item.get("lfs", {}).get("size", 0))
        part = path.with_suffix(path.suffix + ".part")
        if path.exists() and (not size or path.stat().st_size == size):
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()
            if not expected_hash or digest == expected_hash:
                done += path.stat().st_size
                manifest["files"][filename] = digest
                progress(done, total)
                continue
        offset = part.stat().st_size if part.exists() else 0
        request = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{revision}/{filename}", headers={"Range": f"bytes={offset}-", "User-Agent": f"DualLiveCaptions/{__version__}"})
        with urllib.request.urlopen(request, timeout=40) as response:
            append = offset > 0 and response.status == 206
            if not append:
                offset = 0
            with part.open("ab" if append else "wb") as output:
                while not cancelled.is_set():
                    block = response.read(1024 * 512)
                    if not block:
                        break
                    output.write(block)
                    offset += len(block)
                    progress(done + offset, total)
            if cancelled.is_set():
                return None
        digest = hashlib.sha256()
        with part.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if (size and part.stat().st_size != size) or (expected_hash and digest.hexdigest() != expected_hash):
            part.unlink(missing_ok=True)
            raise ValueError("El archivo no superó la verificación de integridad")
        part.replace(path)
        manifest["files"][filename] = digest.hexdigest()
        done += offset
    temporary = root / "verified.tmp"
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(root / "verified.json")
    return str(root)
