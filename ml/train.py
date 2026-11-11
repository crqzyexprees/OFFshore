"""Trains the Category classifier on data/processed/*.parquet.

Writes models/best_model.pt and models/labels.json; export_onnx.py turns them
into a model bundle the app can load.
"""

import json
import os
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import DistilBertTokenizerFast

import _paths  # noqa: F401
from backend.prediction import encode
from backend.vocabulary import CATEGORIES
from model import BASE_MODEL, TxClassifier

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_DIR = Path("models")
DATA = Path("data/processed")


class TxDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, label_ids: dict[str, int]):
        self.df = df.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.label_ids = label_ids

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        e = encode(self.tokenizer, row["description"], int(row["amount_cents"]), row["kind"], row["date"])
        return {
            "input_ids": torch.tensor(e.input_ids),
            "attention_mask": torch.tensor(e.attention_mask),
            "numbers": torch.tensor(e.numbers, dtype=torch.float32),
            "label": torch.tensor(self.label_ids[row["category"]]),
        }


def load_examples() -> pd.DataFrame:
    frames = [pd.read_parquet(DATA / "combined.parquet")]
    if (DATA / "corrections.parquet").exists():
        frames.append(pd.read_parquet(DATA / "corrections.parquet"))
    df = pd.concat(frames, ignore_index=True)
    unknown = set(df["category"]) - set(CATEGORIES)
    if unknown:
        raise SystemExit(f"Labels outside the curated Categories: {sorted(unknown)}")
    return df


def run_epoch(model, loader, optimizer=None, criterion=None):
    training = optimizer is not None
    model.train(training)
    preds, labels, total_loss = [], [], 0.0
    with torch.set_grad_enabled(training):
        for batch in loader:
            y = batch["label"].to(DEVICE)
            logits = model(
                batch["input_ids"].to(DEVICE),
                batch["attention_mask"].to(DEVICE),
                batch["numbers"].to(DEVICE),
            )
            if training:
                loss = criterion(logits, y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * y.size(0)
            preds.extend(logits.argmax(1).cpu().tolist())
            labels.extend(y.cpu().tolist())
    accuracy = sum(p == l for p, l in zip(preds, labels)) / len(labels)
    return total_loss / len(labels), accuracy, preds, labels


def main():
    MODEL_DIR.mkdir(exist_ok=True)
    df = load_examples()
    labels = sorted(df["category"].unique())
    label_ids = {c: i for i, c in enumerate(labels)}
    (MODEL_DIR / "labels.json").write_text(json.dumps(labels))
    print(f"Classes ({len(labels)}): {labels}")

    train_df, val_df = train_test_split(df, test_size=0.1, stratify=df["category"], random_state=42)
    tokenizer = DistilBertTokenizerFast.from_pretrained(BASE_MODEL).backend_tokenizer
    workers = min(4, os.cpu_count() or 1)
    train_loader = DataLoader(TxDataset(train_df, tokenizer, label_ids), batch_size=64,
                              shuffle=True, num_workers=workers, pin_memory=True)
    val_loader = DataLoader(TxDataset(val_df, tokenizer, label_ids), batch_size=64,
                            num_workers=workers, pin_memory=True)

    model = TxClassifier(len(labels)).to(DEVICE)
    criterion = nn.CrossEntropyLoss()

    print("\n── Phase 1: training the heads (BERT frozen) ──")
    for p in model.bert.parameters():
        p.requires_grad = False
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3)
    for epoch in range(3):
        loss, acc, _, _ = run_epoch(model, train_loader, optimizer, criterion)
        print(f"Epoch {epoch + 1}: loss={loss:.4f}, acc={acc:.4f}")

    print("\n── Phase 2: fine-tuning the full model ──")
    for p in model.bert.parameters():
        p.requires_grad = True
    optimizer = torch.optim.AdamW([
        {"params": model.bert.parameters(), "lr": 2e-5},
        {"params": model.number_head.parameters(), "lr": 1e-4},
        {"params": model.classifier.parameters(), "lr": 1e-4},
    ])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=5)
    best = 0.0
    for epoch in range(5):
        loss, train_acc, _, _ = run_epoch(model, train_loader, optimizer, criterion)
        _, val_acc, _, _ = run_epoch(model, val_loader)
        scheduler.step()
        print(f"Epoch {epoch + 1}: loss={loss:.4f}, train_acc={train_acc:.4f}, val_acc={val_acc:.4f}")
        if val_acc > best:
            best = val_acc
            torch.save(model.state_dict(), MODEL_DIR / "best_model.pt")
            print(f"  → Saved best model (val_acc={val_acc:.4f})")

    model.load_state_dict(torch.load(MODEL_DIR / "best_model.pt"))
    _, _, preds, truth = run_epoch(model, val_loader)
    print("\n── Classification report ──")
    print(classification_report(truth, preds, labels=range(len(labels)), target_names=labels))


if __name__ == "__main__":
    main()
