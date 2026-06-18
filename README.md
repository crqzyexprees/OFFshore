# Finance — Local Credit Card Transaction Classifier

A fully local **Electron + Python** desktop app that parses credit card PDF statements, classifies transactions with an on-device ML model, stores everything in SQLite, and visualizes spending across multiple cards.

**No cloud. No telemetry. Everything stays on your machine.**

## Features

- **PDF import** — Chase and generic statement parsers (more banks welcome)
- **On-device ML** — DistilBERT + numeric features via ONNX Runtime (Python)
- **SQLite storage** — Accounts, transactions, duplicate statement detection
- **Spending dashboard** — Category breakdown with donut chart
- **Manual overrides** — Correct categories and retrain with your corrections

## Architecture

```
Electron (UI shell)
    ↓ spawns
Python FastAPI backend (port 18765)
    ├── pdfplumber PDF parsers
    ├── onnxruntime classifier
    └── SQLite database
    ↑
React frontend (Vite) — fetch() to local API
```

## Quick Start

### Prerequisites

- **Node.js** 18+
- **Python** 3.10+

### Install

```bash
# Frontend
npm install

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Run

```bash
npm run dev
```

This starts the Python API, Vite dev server, and Electron window together.

The app runs without a trained model — imports default to **Other** until you complete the ML pipeline.

### Train the classifier (optional)

See [ml/README.md](ml/README.md). After training:

```bash
cp ml/models/classifier.onnx backend/models/
cp ml/models/categories.json backend/models/
cp -r ml/models/tokenizer/ backend/models/tokenizer/
```

## Project Structure

```
├── electron/          # Electron main process + preload
├── backend/           # Python FastAPI — DB, ML inference, PDF parsing
│   ├── parsers/       # Bank-specific PDF parsers
│   └── models/        # ONNX model artifacts (after training)
├── src/               # React frontend
└── ml/                # Training pipeline (not required at runtime)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health check |
| GET | `/api/accounts` | List cards |
| POST | `/api/accounts` | Add card |
| DELETE | `/api/accounts/{id}` | Remove card |
| GET | `/api/transactions` | List transactions |
| GET | `/api/spending/{month}` | Spending by category |
| POST | `/api/transactions/{id}/category` | Override category |
| POST | `/api/import` | Import PDF statement |

## Privacy

- All data stored in `~/.local/share/finance-app/finance.db`
- No network requests at runtime (localhost only)
- Your statements never leave your machine

## License

MIT — see [LICENSE](LICENSE)
