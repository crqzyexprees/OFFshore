"""Exports models/best_model.pt as a model bundle (see backend/prediction.py).

    python export_onnx.py            # writes models/bundle/
    python export_onnx.py --install  # …and copies it into backend/models/
"""

import json
import shutil
import sys
from datetime import date
from pathlib import Path

import torch
from transformers import DistilBertTokenizerFast

import _paths
from backend.prediction import FEATURE_VERSION, encode
from model import BASE_MODEL, TxClassifier

MODEL_DIR = Path("models")
BUNDLE = MODEL_DIR / "bundle"
APP_MODELS = _paths.ROOT / "backend" / "models"

labels = json.loads((MODEL_DIR / "labels.json").read_text())
model = TxClassifier(len(labels))
model.load_state_dict(torch.load(MODEL_DIR / "best_model.pt", map_location="cpu"))
model.eval()

tokenizer = DistilBertTokenizerFast.from_pretrained(BASE_MODEL).backend_tokenizer
e = encode(tokenizer, "whole foods market", 4250, "purchase", date(2026, 1, 15))

BUNDLE.mkdir(parents=True, exist_ok=True)
torch.onnx.export(
    model,
    (torch.tensor([e.input_ids]), torch.tensor([e.attention_mask]), torch.tensor([e.numbers])),
    BUNDLE / "classifier.onnx",
    input_names=["input_ids", "attention_mask", "numbers"],
    output_names=["logits"],
    dynamic_axes={name: {0: "batch"} for name in ("input_ids", "attention_mask", "numbers", "logits")},
    opset_version=14,
)
tokenizer.save(str(BUNDLE / "tokenizer.json"))
(BUNDLE / "bundle.json").write_text(json.dumps({"feature_version": FEATURE_VERSION, "labels": labels}))
print(f"Wrote model bundle to {BUNDLE}/")

if "--install" in sys.argv:
    for name in ("classifier.onnx", "tokenizer.json", "bundle.json"):
        shutil.copy2(BUNDLE / name, APP_MODELS / name)
    print(f"Installed into {APP_MODELS}/")
