"""Collect installed dependency licenses for inclusion in the app bundle."""

from importlib.metadata import distributions
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
output = root / "build/local-notices"
output.mkdir(parents=True, exist_ok=True)
index = []
for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    if name.lower() in {"torch", "voice-input-tool"}:
        continue
    index.append(f"{name} {dist.version}")
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(dist.locate_file(file))
            if source.is_file() and source.suffix not in {".py", ".pyc", ".so"}:
                destination = output / name / str(file).replace("/", "_")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
shutil.copyfile(root / "packaging/Whisper-LICENSE.txt", output / "Whisper-LICENSE.txt")
(output / "DEPENDENCIES.txt").write_text(
    "Build environment dependency notices "
    "(some build-only packages are not bundled).\n\n"
    + "\n".join(index)
    + "\n",
    encoding="utf-8",
)
