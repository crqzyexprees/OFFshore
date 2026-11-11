"""Downloads the sentence-embedding model into backend/models/embedder/.

    python -m backend.prediction.fetch

all-MiniLM-L6-v2 (Apache-2.0), dynamically quantised to int8 (23 MB). The
revision and checksums are pinned, so every build ships the same bytes.
The build runs this before bundling; it's skipped when the files are present.
"""

import hashlib
import sys
import urllib.request

from backend.config import MODEL_DIR

REPO = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
FILES = {
    # local name: (path in the repo, sha256)
    "model.onnx": ("onnx/model_qint8_avx512.onnx",  # identical bytes to the arm64 variant
                   "4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474"),
    "tokenizer.json": ("tokenizer.json",
                       "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037"),
}
TARGET = MODEL_DIR / "embedder"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, (remote, digest) in FILES.items():
        path = TARGET / name
        if path.exists() and _sha256(path) == digest:
            print(f"{name}: already present")
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}"
        print(f"{name}: downloading {url}")
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        if _sha256(partial) != digest:
            partial.unlink()
            sys.exit(f"{name}: checksum mismatch; refusing to install it")
        partial.replace(path)
    print(f"Embedding model ready in {TARGET}")


if __name__ == "__main__":
    fetch()
