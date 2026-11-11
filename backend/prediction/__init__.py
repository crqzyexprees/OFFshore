"""Category prediction: which Category a Purchase or Refund most likely belongs to.

Three adapters sit behind `CategoryPredictor`; `load` picks the best one
installed in the model directory:

- `ExamplePredictor` (examples.py): compares the description with labelled
  examples, the user's own corrections first. Needs models/embedder/
  (`python -m backend.prediction.fetch`).
- `OnnxPredictor` (classifier.py): a classifier trained with ml/.
- `NoModel`: everything is the fallback Category until corrected.
"""

import sys
from pathlib import Path

from backend.prediction.base import CategoryPredictor, NoModel, Prediction, Query, to_category
from backend.prediction.classifier import FEATURE_VERSION, MAX_TOKENS, NUMBERS, Encoded, OnnxPredictor, encode
from backend.prediction.examples import Corrections, ExamplePredictor, clean

__all__ = [
    "CategoryPredictor", "NoModel", "Prediction", "Query", "to_category", "load",
    "ExamplePredictor", "Corrections", "clean",
    "OnnxPredictor", "encode", "Encoded", "FEATURE_VERSION", "MAX_TOKENS", "NUMBERS",
]


def load(model_dir: Path, corrections: Corrections = lambda: []) -> CategoryPredictor:
    """The best predictor installed in `model_dir`. A broken model never stops
    the app; it falls back to the next option."""
    if (model_dir / "embedder" / "model.onnx").exists():
        try:
            from backend.prediction.embedder import Embedder

            predictor = ExamplePredictor(Embedder(model_dir / "embedder"), corrections)
            print(f"Predicting Categories from examples ({model_dir / 'embedder'})", file=sys.stderr)
            return predictor
        except Exception as e:
            print(f"Warning: can't use the embedding model: {e}", file=sys.stderr)
    if (model_dir / "classifier.onnx").exists():
        try:
            predictor = OnnxPredictor(model_dir)
            print(f"Predicting Categories with the trained classifier in {model_dir}", file=sys.stderr)
            return predictor
        except Exception as e:
            print(f"Warning: can't use the model bundle in {model_dir}: {e}", file=sys.stderr)
    print(f"No model in {model_dir}; Categories default to Other until corrected", file=sys.stderr)
    return NoModel()
