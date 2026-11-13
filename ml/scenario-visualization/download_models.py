"""Download pinned, safetensors-only assets with the Hugging Face CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / "models.lock.json").read_text())
    env = dict(os.environ, HF_HOME=str(ROOT / ".local/hf"),
               HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_XET="1",
               HF_HUB_DOWNLOAD_TIMEOUT="60")
    cli = Path(sys.executable).parent / "hf"
    for model in manifest["models"]:
        dest = ROOT / ".local/models" / model["name"]
        subprocess.run([
            str(cli), "download", model["repo_id"],
            *[item["path"] for item in model["files"]],
            "--revision", model["revision"], "--local-dir", str(dest),
            "--max-workers", "3",
        ], env=env, check=True)
        for item in model["files"]:
            path = dest / item["path"]
            if path.stat().st_size != item["size"]:
                raise RuntimeError(f"Size mismatch: {path}")
            if item["sha256"]:
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != item["sha256"]:
                    raise RuntimeError(f"Checksum mismatch: {path}")
        print(f"Verified {model['name']} assets", flush=True)


if __name__ == "__main__":
    main()
