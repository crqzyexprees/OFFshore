# Models (not committed)

- `embedder/` — the sentence-embedding model used to predict Categories from
  examples. Fetch it with `python -m backend.prediction.fetch` (the package
  build does this automatically).
- `classifier.onnx`, `tokenizer.json`, `bundle.json` — optional: a classifier
  trained with ml/ (`python export_onnx.py --install`). Used only when there is
  no embedder.

Everything here is bundled into the packages at build time. With neither
installed, Purchases and Refunds get the Category "Other" until corrected.
