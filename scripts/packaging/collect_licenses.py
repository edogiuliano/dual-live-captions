from pathlib import Path
import importlib.metadata
import json
import shutil
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--destination")
options = parser.parse_args()
root = Path(options.destination) if options.destination else Path(__file__).resolve().parents[2] / "dist/DualLiveCaptions/THIRD_PARTY"
root.mkdir(parents=True, exist_ok=True)
manifest = []
for dist in importlib.metadata.distributions():
    name = dist.metadata.get("Name", "unknown")
    files = []
    for file in dist.files or []:
        if any(part.lower() in ("licenses", "license", "copying", "notice") for part in file.parts) or file.name.lower().startswith(("license", "copying", "notice")):
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = root / name / str(file).replace("../", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                files.append(str(target.relative_to(root)))
    manifest.append({"name": name, "version": dist.version, "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"), "files": files})
(root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
