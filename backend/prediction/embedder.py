"""Sentence embeddings: text → a unit vector, where similar meanings are close."""

from pathlib import Path


class Embedder:
    """all-MiniLM-L6-v2 as ONNX (fetched by backend.prediction.fetch)."""

    MAX_TOKENS = 64

    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(self.MAX_TOKENS)
        self.tokenizer.enable_padding()
        self.session = ort.InferenceSession(str(directory / "model.onnx"), providers=["CPUExecutionProvider"])

    def embed(self, texts: list[str]):
        """An (n, 384) array of unit vectors."""
        import numpy as np

        encodings = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        (hidden,) = self.session.run(
            ["last_hidden_state"],
            {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)},
        )
        # Mean of the real (unpadded) tokens, as the model was trained.
        weights = mask[:, :, None].astype(np.float32)
        pooled = (hidden * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
        return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
