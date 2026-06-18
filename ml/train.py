import os
import pickle

import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import DataLoader, Dataset
from transformers import DistilBertModel, DistilBertTokenizerFast

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

df = pd.read_parquet("data/processed/combined.parquet")

# Subsample for faster iteration during development (remove for final training)
# df = df.sample(n=500_000, random_state=42)

le = LabelEncoder()
df["label"] = le.fit_transform(df["category"])
NUM_CLASSES = len(le.classes_)

with open(f"{MODEL_DIR}/label_encoder.pkl", "wb") as f:
    pickle.dump(le, f)

print(f"Classes ({NUM_CLASSES}): {le.classes_}")

train_df, val_df = train_test_split(
    df, test_size=0.1, stratify=df["label"], random_state=42
)

tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")


class TxDataset(Dataset):
    def __init__(self, df, tokenizer, max_len=32):
        self.df = df.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        text = str(row["merchant_text"]) if row["merchant_text"] else "[PAD]"

        enc = self.tokenizer(
            text,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        num_features = torch.tensor(
            [
                float(row["amount"]),
                float(row["hour"]) / 23.0,
                float(row["day_of_week"]) / 6.0,
                float(row["month"]) / 12.0,
                float(row["use_chip_enc"]) / 3.0,
            ],
            dtype=torch.float32,
        )

        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "num_features": num_features,
            "label": torch.tensor(row["label"], dtype=torch.long),
        }


train_ds = TxDataset(train_df, tokenizer)
val_ds = TxDataset(val_df, tokenizer)

train_loader = DataLoader(
    train_ds, batch_size=64, shuffle=True, num_workers=4, pin_memory=True
)
val_loader = DataLoader(
    val_ds, batch_size=64, shuffle=False, num_workers=4, pin_memory=True
)


class TxClassifier(nn.Module):
    def __init__(self, num_classes, num_numeric_features=5):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained("distilbert-base-uncased")

        for param in self.bert.parameters():
            param.requires_grad = False

        self.num_head = nn.Sequential(
            nn.Linear(num_numeric_features, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
        )

        self.classifier = nn.Sequential(
            nn.Linear(768 + 32, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask, num_features):
        bert_out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_token = bert_out.last_hidden_state[:, 0, :]
        num_out = self.num_head(num_features)
        combined = torch.cat([cls_token, num_out], dim=1)
        return self.classifier(combined)


model = TxClassifier(NUM_CLASSES).to(DEVICE)

optimizer = torch.optim.AdamW(
    [p for p in model.parameters() if p.requires_grad], lr=1e-3
)
criterion = nn.CrossEntropyLoss()


def train_epoch(loader):
    model.train()
    total_loss, correct, total = 0, 0, 0
    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attn_mask = batch["attention_mask"].to(DEVICE)
        num_feat = batch["num_features"].to(DEVICE)
        labels = batch["label"].to(DEVICE)

        optimizer.zero_grad()
        logits = model(input_ids, attn_mask, num_feat)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * labels.size(0)
        correct += (logits.argmax(1) == labels).sum().item()
        total += labels.size(0)

    return total_loss / total, correct / total


def eval_epoch(loader):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(DEVICE)
            attn_mask = batch["attention_mask"].to(DEVICE)
            num_feat = batch["num_features"].to(DEVICE)
            labels = batch["label"].to(DEVICE)
            logits = model(input_ids, attn_mask, num_feat)
            all_preds.extend(logits.argmax(1).cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    return all_preds, all_labels


print("\n── Phase 1: Training head only (BERT frozen) ──")
for epoch in range(3):
    loss, acc = train_epoch(train_loader)
    print(f"Epoch {epoch + 1}: loss={loss:.4f}, acc={acc:.4f}")

print("\n── Phase 2: Fine-tuning full model ──")
for param in model.bert.parameters():
    param.requires_grad = True

optimizer = torch.optim.AdamW(
    [
        {"params": model.bert.parameters(), "lr": 2e-5},
        {"params": model.num_head.parameters(), "lr": 1e-4},
        {"params": model.classifier.parameters(), "lr": 1e-4},
    ]
)

scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=5)

best_acc = 0
for epoch in range(5):
    loss, train_acc = train_epoch(train_loader)
    preds, labels = eval_epoch(val_loader)
    val_acc = sum(p == l for p, l in zip(preds, labels)) / len(labels)
    scheduler.step()

    print(
        f"Epoch {epoch + 1}: loss={loss:.4f}, train_acc={train_acc:.4f}, val_acc={val_acc:.4f}"
    )

    if val_acc > best_acc:
        best_acc = val_acc
        torch.save(model.state_dict(), f"{MODEL_DIR}/best_model.pt")
        print(f"  → Saved best model (val_acc={val_acc:.4f})")

model.load_state_dict(torch.load(f"{MODEL_DIR}/best_model.pt"))
preds, labels = eval_epoch(val_loader)
print("\n── Classification Report ──")
print(classification_report(labels, preds, target_names=le.classes_))
