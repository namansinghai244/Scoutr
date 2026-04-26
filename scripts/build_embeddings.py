"""
scripts/build_embeddings.py

Reads products from data/products.db, generates sentence embeddings, and saves
a FAISS vector index to data/faiss_index.bin plus a product ID mapping to
data/faiss_ids.json.

Examples:
    python scripts/build_embeddings.py
    python scripts/build_embeddings.py --max-products 200000 --min-rating 3.5
"""

import argparse
import json
import logging
import sqlite3
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = Path("data/products.db")
INDEX_PATH = Path("data/faiss_index.bin")
IDS_PATH = Path("data/faiss_ids.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 512


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Scoutr FAISS index")
    parser.add_argument(
        "--max-products",
        type=int,
        default=None,
        help="Maximum number of products to embed",
    )
    parser.add_argument(
        "--min-rating",
        type=float,
        default=None,
        help="Only include products with this rating or higher, while still keeping unrated products",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="SentenceTransformer batch size",
    )
    return parser.parse_args()


def build_search_text(row: dict) -> str:
    """Combines product fields into a single string for embedding."""
    parts = []
    if row.get("name"):
        parts.append(row["name"])
    if row.get("brand") and row["brand"] not in (row.get("name", "") or ""):
        parts.append(row["brand"])
    if row.get("category"):
        parts.append(row["category"])
    if row.get("sub_category"):
        parts.append(row["sub_category"])
    if row.get("description"):
        parts.append(str(row["description"])[:200])
    return " | ".join(filter(None, parts))


def load_rows(conn: sqlite3.Connection, args: argparse.Namespace) -> list[dict]:
    conditions = [
        "name IS NOT NULL",
        "name != ''",
        "(discounted_price IS NOT NULL OR actual_price IS NOT NULL)",
    ]
    params: list[object] = []

    if args.min_rating is not None:
        conditions.append("(rating >= ? OR rating IS NULL)")
        params.append(args.min_rating)

    query = f"""
        SELECT id, name, brand, category, sub_category, description
        FROM products
        WHERE {' AND '.join(conditions)}
        ORDER BY (rating_count IS NULL) ASC, rating_count DESC, id ASC
    """
    if args.max_products is not None:
        query += "\nLIMIT ?"
        params.append(args.max_products)

    cur = conn.cursor()
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def main() -> None:
    args = parse_args()

    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        log.error("Missing dependencies. Run:")
        log.error("  pip install sentence-transformers faiss-cpu numpy")
        return

    if not DB_PATH.exists():
        log.error(f"Database not found: {DB_PATH}")
        log.error("Run: python scripts/ingest_products.py first")
        return

    log.info("Loading products from database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = load_rows(conn, args)
    conn.close()
    log.info(f"  {len(rows):,} products loaded")

    if not rows:
        log.error("No products found for the selected filters.")
        return

    texts = [build_search_text(row) for row in rows]
    ids = [row["id"] for row in rows]

    log.info(f"Loading embedding model: {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    log.info(
        f"Generating embeddings in batches of {args.batch_size} "
        f"for {len(texts):,} products ..."
    )
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    log.info(f"  Shape: {embeddings.shape}")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    log.info(f"  FAISS index built: {index.ntotal:,} vectors, {dim} dimensions")

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    IDS_PATH.write_text(json.dumps(ids), encoding="utf-8")

    log.info(f"Saved: {INDEX_PATH} ({INDEX_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    log.info(f"Saved: {IDS_PATH}")
    log.info("Next step: your backend will auto-load these at startup.")


if __name__ == "__main__":
    main()
