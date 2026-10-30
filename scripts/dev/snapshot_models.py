"""Record public model metadata and checksum of cached test weights."""
import hashlib
import json
from pathlib import Path
import urllib.request
from dual_live_captions.models import cached_model

root = Path(__file__).resolve().parents[2]
rows = []
for repository in ("Qwen/Qwen3-ASR-0.6B", "nvidia/parakeet-tdt-0.6b-v3", "Systran/faster-whisper-small", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"):
    with urllib.request.urlopen("https://huggingface.co/api/models/" + repository, timeout=30) as response:
        data = json.load(response)
    rows.append({"repository": repository, "revision": data["sha"], "license": data.get("cardData", {}).get("license"), "last_modified": data.get("lastModified")})
for model in ("base", "small"):
    path = Path(cached_model(model)) / "model.bin"
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    rows.append({"tested_model": model, "sha256": hasher.hexdigest(), "bytes": path.stat().st_size})
(root / "docs/research/model-revisions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(json.dumps(rows, indent=2))
