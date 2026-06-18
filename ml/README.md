# ML Training Pipeline

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
python export_onnx.py

cp models/classifier.onnx ../backend/models/
cp models/categories.json ../backend/models/
cp -r models/tokenizer/ ../backend/models/tokenizer/
```

## Retraining with User Corrections

After using the app and overriding categories:

```bash
python export_corrections.py
python train.py
python export_onnx.py
```
