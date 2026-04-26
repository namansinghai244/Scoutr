# Scoutr v2 — Dataset Integration Setup

## Overview

Scoutr v2 uses real product data from Kaggle instead of letting the AI invent products.
The AI now only writes explanations for real products retrieved from the database.

## Architecture

```
Kaggle datasets (5 sources)
         ↓
scripts/download_datasets.py    → downloads CSVs to data/datasets/
         ↓
scripts/ingest_products.py      → normalises + loads into data/products.db
         ↓
scripts/build_embeddings.py     → builds FAISS index at data/faiss_index.bin
         ↓
services/db_service.py          → serves hybrid search at runtime
         ↓
services/ai_service.py          → passes real products to AI for explanation
```

## Datasets Integrated

| # | Dataset | Products | Reviews | Store |
|---|---------|----------|---------|-------|
| 1 | karkavelrajaj/amazon-sales-dataset | 1,465 | Yes | Amazon India |
| 2 | lokeshparab/amazon-products-dataset | 300,000+ | Partial | Amazon India |
| 3 | asaniczka/amazon-products-dataset-2023-1-4m-products | 1,400,000 | No | Amazon US |
| 4 | PromptCloudHQ/flipkart-products | 20,000 | No | Flipkart |
| 5 | niraliivaghani/flipkart-dataset | — | 363,000 | Flipkart |

## Setup Steps

### Step 1 — Install Kaggle CLI
```bash
pip install kaggle
```

### Step 2 — Add Kaggle credentials
Get your API token from kaggle.com > Settings > API > Create New Token.
Place kaggle.json at: C:\Users\<you>\.kaggle\kaggle.json
OR add to .env:
```
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_api_key
```

### Step 3 — Download all datasets
```bash
python scripts/download_datasets.py
```
This downloads ~5GB total. Datasets 1 and 4 are small (< 5MB each).
Dataset 3 (1.4M products) is the largest at ~3GB.

### Step 4 — Ingest into SQLite
```bash
python scripts/ingest_products.py
```
Creates data/products.db. Takes 5-15 minutes depending on how many datasets you downloaded.

### Step 5 — Build vector index
```bash
pip install sentence-transformers faiss-cpu numpy
python scripts/build_embeddings.py
```
Creates data/faiss_index.bin and data/faiss_ids.json.
Takes 10-30 minutes for 1M+ products on CPU.

### Step 6 — Run the server
```bash
python main.py
```
The server auto-loads the database and FAISS index at startup.
You will see: "ProductDB ready — X vectors"

## Graceful Degradation

If products.db or faiss_index.bin are not present, the server falls back
to AI-only mode automatically. The app keeps working — just with AI-generated
product names instead of real database products.

## Deploying to Render

The data files (products.db, faiss_index.bin) are too large to commit to Git.
Two options:

Option A (Recommended): Commit just the CSV files to a separate private repo
or use Render's persistent disk feature to store them.

Option B: Add a build step in render.yaml that runs the download + ingest scripts
at deploy time. Add KAGGLE_USERNAME and KAGGLE_KEY as environment variables in Render.
