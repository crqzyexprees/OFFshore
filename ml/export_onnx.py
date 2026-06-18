import json
import pickle

import torch
from transformers import DistilBertTokenizerFast

from train import TxClassifier

MODEL_DIR = "models"

with open(f"{MODEL_DIR}/label_encoder.pkl", "rb") as f:
    le = pickle.load(f)

model = TxClassifier(len(le.classes_))
model.load_state_dict(torch.load(f"{MODEL_DIR}/best_model.pt", map_location="cpu"))
model.eval()

tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
tokenizer.save_pretrained(f"{MODEL_DIR}/tokenizer")

dummy_text = "whole foods market"
dummy_enc = tokenizer(
    dummy_text,
    max_length=32,
    padding="max_length",
    truncation=True,
    return_tensors="pt",
)
dummy_num = torch.zeros(1, 5)

torch.onnx.export(
    model,
    (dummy_enc["input_ids"], dummy_enc["attention_mask"], dummy_num),
    f"{MODEL_DIR}/classifier.onnx",
    input_names=["input_ids", "attention_mask", "num_features"],
    output_names=["logits"],
    dynamic_axes={
        "input_ids": {0: "batch"},
        "attention_mask": {0: "batch"},
        "num_features": {0: "batch"},
        "logits": {0: "batch"},
    },
    opset_version=14,
)

print("Exported to models/classifier.onnx")

with open(f"{MODEL_DIR}/categories.json", "w") as f:
    json.dump(list(le.classes_), f)
print("Saved models/categories.json")
