"""The classifier network. Importing this never trains anything."""

import torch
import torch.nn as nn
from transformers import DistilBertModel

import _paths  # noqa: F401
from backend.prediction import NUMBERS

BASE_MODEL = "distilbert-base-uncased"


class TxClassifier(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained(BASE_MODEL)
        self.number_head = nn.Sequential(
            nn.Linear(len(NUMBERS), 64),
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

    def forward(self, input_ids, attention_mask, numbers):
        hidden = self.bert(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        cls = hidden[:, 0, :]  # backend.prediction.encode always puts [CLS] first
        return self.classifier(torch.cat([cls, self.number_head(numbers)], dim=1))
