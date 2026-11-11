"""A trained classifier (ml/): the one definition of how a Transaction becomes
its input. Training and the app both call `encode`, so what the model sees in
training is exactly what it sees in use.

A model bundle is a directory holding:
    classifier.onnx   inputs input_ids, attention_mask, numbers; output logits
    tokenizer.json    a `tokenizers` tokenizer that adds [CLS] … [SEP]
    bundle.json       {"feature_version": FEATURE_VERSION, "labels": [Category, ...]}
"""

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.prediction.base import OneAtATime, to_category

# Bump whenever `encode` changes: a bundle trained on other features is refused.
FEATURE_VERSION = 2
MAX_TOKENS = 32
# Only what every Statement prints: no time of day, no chip/swipe.
NUMBERS = ("signed_log_amount", "day_of_week", "month")


@dataclass(frozen=True)
class Encoded:
    input_ids: list[int]
    attention_mask: list[int]
    numbers: list[float]


def encode(tokenizer, description: str, amount_cents: int, kind: str, when: date) -> Encoded:
    """Model input for one Transaction. `tokenizer` is a `tokenizers.Tokenizer`
    (in training, a Hugging Face tokenizer's `.backend_tokenizer`).

    A Refund's amount is negative, so the model can tell it from a Purchase.
    """
    enc = tokenizer.encode(description.strip().lower(), add_special_tokens=True)
    ids = list(enc.ids)
    if len(ids) > MAX_TOKENS:
        ids = ids[: MAX_TOKENS - 1] + ids[-1:]  # keep the closing [SEP]
    mask = [1] * len(ids)
    pad = tokenizer.token_to_id("[PAD]") or 0
    ids += [pad] * (MAX_TOKENS - len(ids))
    mask += [0] * (MAX_TOKENS - len(mask))

    dollars = amount_cents / 100 * (-1 if kind == "refund" else 1)
    numbers = [
        math.copysign(math.log1p(abs(dollars)), dollars),
        when.weekday() / 6,
        (when.month - 1) / 11,
    ]
    return Encoded(ids, mask, numbers)


class OnnxPredictor(OneAtATime):
    def __init__(self, model_dir: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        bundle = json.loads((model_dir / "bundle.json").read_text())
        if bundle.get("feature_version") != FEATURE_VERSION:
            raise ValueError(
                f"model bundle uses features v{bundle.get('feature_version')}, "
                f"this app needs v{FEATURE_VERSION}; retrain it"
            )
        self.labels: list[str] = bundle["labels"]
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.session = ort.InferenceSession(
            str(model_dir / "classifier.onnx"), providers=["CPUExecutionProvider"]
        )

    def predict(self, description, amount_cents, kind, when):
        import numpy as np

        e = encode(self.tokenizer, description, amount_cents, kind, when)
        (logits,) = self.session.run(
            ["logits"],
            {
                "input_ids": np.array([e.input_ids], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask], dtype=np.int64),
                "numbers": np.array([e.numbers], dtype=np.float32),
            },
        )
        scores = logits[0] - logits[0].max()
        probs = np.exp(scores) / np.exp(scores).sum()
        best = int(probs.argmax())
        return to_category(self.labels[best], float(probs[best]))
