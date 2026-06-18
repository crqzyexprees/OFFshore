import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class TxClassifier:
    def __init__(self, model_dir: Path):
        onnx_path = model_dir / "classifier.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(
                f"Model not found at {onnx_path}. Run the ML pipeline in ml/."
            )

        self.session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        tokenizer_path = model_dir / "tokenizer" / "tokenizer.json"
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        with open(model_dir / "categories.json") as f:
            self.categories: list[str] = json.load(f)

    def classify(
        self,
        merchant_text: str,
        amount: float,
        hour: float = 12.0,
        day_of_week: float = 3.0,
        month: float = 6.0,
        use_chip: float = 3.0,
    ) -> tuple[str, float]:
        encoding = self.tokenizer.encode(merchant_text, add_special_tokens=False)
        max_len = 32
        ids = list(encoding.ids)
        mask = list(encoding.attention_mask)
        ids = (ids + [0] * max_len)[:max_len]
        mask = (mask + [0] * max_len)[:max_len]

        num_features = np.array(
            [[amount, hour / 23.0, day_of_week / 6.0, month / 12.0, use_chip / 3.0]],
            dtype=np.float32,
        )

        outputs = self.session.run(
            None,
            {
                "input_ids": np.array([ids], dtype=np.int64),
                "attention_mask": np.array([mask], dtype=np.int64),
                "num_features": num_features,
            },
        )
        logits = outputs[0][0]
        max_logit = float(np.max(logits))
        exps = np.exp(logits - max_logit)
        probs = exps / exps.sum()
        best_idx = int(np.argmax(probs))
        return self.categories[best_idx], float(probs[best_idx])
