# SplitLens — Local Spending Tracker

A fully local desktop app (**Tauri + React** UI, **Python** backend) that reads credit card and bank PDF Statements, predicts each transaction's Category on-device (learning from your corrections), stores everything in SQLite, and visualizes spending across your Accounts.

**No cloud. No telemetry. Everything stays on your machine.**

## Features

- **PDF import** — finds the Account, billing period and Transactions; bad lines are reported, never silently stored
- **CSV / OFX / QFX import** — bank Exports; OFX files name their Account and period, CSV files ask for them
- **On-device Category prediction** — a small sentence-embedding model (MiniLM, ONNX Runtime) matches each transaction to its most similar labelled example, your own corrections first
- **SQLite storage** — Accounts, transactions, duplicate statement detection
- **Spending dashboard** — Category breakdown with donut chart
- **Credit cards and bank accounts** — every Transaction is a Purchase, Refund, Transfer, Income, Withdrawal or Reward (see [GLOSSARY.md](GLOSSARY.md))
- **Backups** — save everything to `~/Documents/SplitLens Backups/`, optionally encrypted with a password (scrypt + AES-256-GCM); restoring keeps a copy of the data it replaces
- **Overrides** — correct a Transaction's kind or Category; re-importing a Statement keeps them

## Architecture

```
Tauri shell (Rust, src-tauri/)
    ├── window: React frontend (Vite) rendered by WebKitGTK
    └── spawns the Python backend as a sidecar process
          python -m backend --sidecar
            ├── FastAPI on a random 127.0.0.1 port, per-launch auth token
            ├── Statement import (pdfplumber)
            ├── Category prediction (onnxruntime)
            └── SQLite database
```

The shell reads the backend's port and token from its stdout and hands them to the UI.
The backend exits when the shell does (it watches its stdin), even if the shell crashes.

## Quick Start

### Prerequisites

- **Node.js** 18+, **Python** 3.10+, **Rust** (stable, via [rustup](https://rustup.rs))
- Tauri's Linux build dependencies — on Fedora:
  `sudo dnf install webkit2gtk4.1-devel openssl-devel librsvg2-devel`
  (others: see the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/))

### Install

```bash
npm install
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
```

### Develop

```bash
npm run app:dev    # desktop app with hot reload (Tauri runs .venv/bin/python as the backend)
npm run dev        # or: browser only — API + Vite, open http://localhost:1420
```

Fetch the embedding model once (23 MB, pinned and checksummed; the package build does this itself):

```bash
.venv/bin/python -m backend.prediction.fetch
```

Without it the app still runs, and Categories default to **Other** until corrected.

### Build the Linux packages

```bash
npm run app:build
```

Builds in an Ubuntu 22.04 container with [podman](https://podman.io), so the AppImage runs on
distros from ~2022 onward regardless of what you build on. Output in `release/`:

| File | Use it on |
|------|-----------|
| `SplitLens_*.AppImage` | Any distro — `chmod +x` and run, or manage it with [Gear Lever](https://flathub.org/apps/it.mijorus.gearlever) |
| `SplitLens-*.x86_64.rpm` | Fedora — uses the system's WebKit, the most reliable option on NVIDIA |
| `SplitLens_*_amd64.deb` | Debian / Ubuntu |

The Python backend is bundled with PyInstaller (`packaging/splitlens-backend.spec`), so nothing
needs to be installed on the target machine. The first build takes a while; dependency caches are
kept in podman volumes (`splitlens-build-*`) so later builds are faster.

### Graphics problems (blank window, NVIDIA)

WebKitGTK has known rendering bugs with some drivers. The app handles them in layers:

1. **NVIDIA detected** (`/proc/driver/nvidia/version`): sets `__NV_DISABLE_EXPLICIT_SYNC=1` on
   Wayland or `WEBKIT_DISABLE_DMABUF_RENDERER=1` on X11.
2. **Safe mode**: if the window hasn't loaded within 12 seconds, the app saves `safe_mode` to
   `~/.config/app.splitlens/settings.json` and restarts with software rendering. Toggle it
   under **Settings**, or launch once with `--safe-mode`.
3. **Native packages**: if the AppImage still misbehaves, use the `.rpm`/`.deb`.

Variables you set yourself are never overridden. The app logs what it applied to stderr:
`[splitlens] graphics: nvidia=… wayland=… safe_mode=… set=[…]`.

### How Categories are predicted

Each Purchase or Refund takes the Category of its most similar labelled example
(`backend/prediction/`): your own corrections first, then a built-in starter set.
Correcting one transaction re-predicts the others you haven't edited, so the
rest of that merchant's transactions follow. To measure it on your own data:

```bash
cd ml && ../.venv/bin/python evaluate.py export labelled.csv   # fix the category column, then:
../.venv/bin/python evaluate.py score labelled.csv
```

A trained classifier (`ml/`, needs torch and the Kaggle datasets) is still
supported and used when no embedding model is installed; see
[ml/README.md](ml/README.md) and [docs/adr/0006](docs/adr/0006-predict-categories-from-examples.md).

## Project Structure

```
├── src-tauri/         # Tauri shell — window, sidecar management, graphics workarounds
├── backend/           # Python — FastAPI, DB, ML inference
│   ├── statement_import/  # Statement import: reading, validation, kinds, replacing
│   └── models/        # embedding model (fetched) or a trained model bundle
├── tests/             # pytest (`.venv/bin/python -m pytest`)
├── docs/adr/          # Architecture decision records
├── GLOSSARY.md        # Domain language: Account, Statement, Transaction, ...
├── src/               # React frontend
├── packaging/         # Container build, PyInstaller spec, icon source
└── ml/                # Training pipeline (not required at runtime)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health check |
| GET | `/api/reference` | Banks, Transaction kinds and Categories |
| GET | `/api/accounts` | List Accounts |
| POST | `/api/accounts` | Add an Account (`kind`: `credit_card` or `bank`) |
| DELETE | `/api/accounts/{id}` | Remove an Account and its Statements |
| GET | `/api/transactions` | List Transactions (filters: `account_id`, `month`, `category`, `kind`) |
| GET | `/api/spending/{month}` | Spending per Category (Purchases − Refunds) and cash withdrawn |
| POST | `/api/transactions/{id}/override` | Set or clear the Override (`kind`, `category`) |
| GET | `/api/backups` | Where Backups are saved |
| POST | `/api/backups` | Save a Backup (`password` optional; without one it's a plain SQLite copy) |
| POST | `/api/restore` | Replace all data with a Backup (multipart: `file`, `password` if encrypted) |
| POST | `/api/import` | Import a Statement — PDF, CSV, OFX or QFX (multipart: `file`, optional `account_id`, `period_start`, `period_end`) |

An import the backend can't complete on its own returns `422` with a `problem` code:
`needs_account`, `needs_period`, `account_mismatch` or `no_transactions`. Nothing is stored.

## Privacy

- All data stored in `~/.local/share/splitlens/splitlens.db` (data from before the rename, in `~/.local/share/finance-app/`, is moved there on first start)
- Backups without a password are readable by anyone who has the file; encrypted ones need the password, which is never stored
- No network requests at runtime (localhost only)
- The API listens on `127.0.0.1` only, requires a random per-launch token, and only allows the app's own origin (CORS), so other programs and websites can't use it
- Your statements never leave your machine

## License

MIT — see [LICENSE](LICENSE)
