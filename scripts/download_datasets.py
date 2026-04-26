"""
scripts/download_datasets.py
Downloads all 5 Kaggle datasets needed for Scoutr v2.

Run once:
    python scripts/download_datasets.py

Requirements:
    pip install kaggle
    Place kaggle.json at C:/Users/<you>/.kaggle/kaggle.json
    OR set KAGGLE_USERNAME and KAGGLE_KEY in your .env
"""

import os
import sys
import subprocess
from pathlib import Path

ENV_PATH = Path(".env")

DATASETS = [
    {
        "id":       "karkavelrajaj/amazon-sales-dataset",
        "name":     "Amazon Sales India — 1.4k products + reviews + images + ASINs",
        "slug":     "amazon_sales",
        "priority": 1,
    },
    {
        "id":       "lokeshparab/amazon-products-dataset",
        "name":     "Amazon Products 2023 — 300k products, 142 categories",
        "slug":     "amazon_products_2023",
        "priority": 2,
    },
    {
        "id":       "asaniczka/amazon-products-dataset-2023-1-4m-products",
        "name":     "Amazon Products 2023 — 1.4M products with ASIN, price, Prime status",
        "slug":     "amazon_1_4m",
        "priority": 3,
    },
    {
        "id":       "PromptCloudHQ/flipkart-products",
        "name":     "Flipkart Products — 20k Indian products with specs",
        "slug":     "flipkart_products",
        "priority": 4,
    },
    {
        "id":       "niraliivaghani/flipkart-dataset",
        "name":     "Flipkart Reviews — 363k reviews with sentiment",
        "slug":     "flipkart_reviews",
        "priority": 5,
    },
]

OUTPUT_DIR = Path("data/datasets")


def load_dotenv() -> None:
    """Minimal .env loader so Kaggle creds work for the setup flow."""
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def check_kaggle_auth():
    config_dir = Path(os.getenv("KAGGLE_CONFIG_DIR", str(Path.home() / ".kaggle")))
    kaggle_json = config_dir / "kaggle.json"
    access_token = config_dir / "access_token"
    has_json = kaggle_json.exists()
    has_env = bool(os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))
    has_token_env = bool(os.getenv("KAGGLE_API_TOKEN"))
    has_token_file = access_token.exists()
    if not has_json and not has_env and not has_token_env and not has_token_file:
        print("\nERROR: Kaggle credentials not found.")
        print("Option A: Go to kaggle.com > Your Profile > Settings > API > Create Token")
        print(f"          Place kaggle.json at: {kaggle_json}")
        print("Option B: Add to .env: KAGGLE_USERNAME=xxx and KAGGLE_KEY=xxx")
        print("Option C: Set KAGGLE_API_TOKEN or place access_token in KAGGLE_CONFIG_DIR")
        sys.exit(1)
    print("Kaggle credentials found.")


def download_dataset(d: dict, output_dir: Path):
    dest = output_dir / d["slug"]
    if dest.exists() and any(dest.iterdir()):
        print(f"  [SKIP] Already downloaded: {dest}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    print(f"  [DOWNLOADING] {d['name']} ...")
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", d["id"], "-p", str(dest), "--unzip"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        files = list(dest.glob("*"))
        print(f"  [DONE] {len(files)} file(s) at {dest}/")
        for f in files[:5]:
            print(f"         {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print(f"  [FAILED] {result.stderr.strip()}")


def main():
    print("=" * 60)
    print("Scoutr v2 — Dataset Downloader")
    print("=" * 60)
    load_dotenv()
    check_kaggle_auth()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for d in sorted(DATASETS, key=lambda x: x["priority"]):
        print(f"\nPriority {d['priority']}: {d['name']}")
        download_dataset(d, OUTPUT_DIR)
    print("\nAll downloads complete.")
    print("Next step: python scripts/ingest_products.py")


if __name__ == "__main__":
    main()
