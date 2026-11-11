# ML Training Pipeline

> The app predicts Categories from examples by default (docs/adr/0006); a model
> trained here is only used when no embedding model is installed.
> `evaluate.py` (scoring the app's predictions on your own labelled data) needs
> only the backend's dependencies.

Python scripts for training the on-device transaction classifier. **Not shipped with the app.**

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Datasets

Download from Kaggle (requires `~/.kaggle/kaggle.json`):

1. [Priyamchoksi/Sparkov](https://www.kaggle.com/datasets/priyamchoksi/credit-card-transactions-dataset) → `data/raw/credit_card_transactions.csv`
2. [IBM/ealtman2019](https://www.kaggle.com/datasets/ealtman2019/credit-card-transactions) → `data/raw/credit_card_transactions-ibm_v2.csv`

```bash
pip install kaggle
kaggle datasets download priyamchoksi/credit-card-transactions-dataset -p data/raw/
kaggle datasets download ealtman2019/credit-card-transactions -p data/raw/
cd data/raw && unzip '*.zip'
```

## Train & Export

```bash
python prepare_data.py
python train.py
python export_onnx.py --install   # writes models/bundle/ and copies it into backend/models/
```

Training encodes every example with `backend.prediction.encode`, the same code
the app uses, so the two can't drift apart. Change the features there and bump
`FEATURE_VERSION`: the app refuses a bundle trained on other features.

## Retraining with User Corrections

After correcting Categories in the app:

```bash
python export_corrections.py      # rewrites data/processed/corrections.parquet
python train.py
python export_onnx.py --install
```
