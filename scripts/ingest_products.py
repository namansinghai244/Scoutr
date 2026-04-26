"""
scripts/ingest_products.py
Reads all downloaded Kaggle CSVs, normalises them into a unified schema,
and writes everything into data/products.db (SQLite).

Run after download_datasets.py:
    python scripts/ingest_products.py

Output: data/products.db with tables:
    products  — one row per product
    reviews   — one row per review linked to a product
"""

import re
import sqlite3
import logging
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH      = Path("data/products.db")
DATASETS_DIR = Path("data/datasets")

# ── Schema ────────────────────────────────────────────────────────────────────
CREATE_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,          -- which dataset this came from
    source_id       TEXT,                   -- original ID in source (ASIN, etc)
    name            TEXT NOT NULL,
    brand           TEXT,
    category        TEXT,
    sub_category    TEXT,
    description     TEXT,
    actual_price    REAL,                   -- original / MRP price
    discounted_price REAL,                  -- current / selling price
    currency        TEXT DEFAULT 'INR',
    discount_pct    REAL,
    rating          REAL,
    rating_count    INTEGER,
    image_url       TEXT,
    product_url     TEXT,
    store           TEXT,                   -- amazon / flipkart
    is_available    INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_REVIEWS = """
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    reviewer    TEXT,
    title       TEXT,
    body        TEXT,
    rating      REAL,
    sentiment   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category);",
    "CREATE INDEX IF NOT EXISTS idx_products_store       ON products(store);",
    "CREATE INDEX IF NOT EXISTS idx_products_price       ON products(discounted_price);",
    "CREATE INDEX IF NOT EXISTS idx_products_rating      ON products(rating);",
    "CREATE INDEX IF NOT EXISTS idx_products_source_id   ON products(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_product_id   ON reviews(product_id);",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def clean_price(val) -> float | None:
    """Strip currency symbols and commas, return float."""
    if pd.isna(val):
        return None
    s = str(val).replace("₹", "").replace("$", "").replace(",", "").strip()
    s = re.sub(r"[^0-9.]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def clean_pct(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def clean_rating(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).split()[0].strip()
    try:
        v = float(s)
        return v if 0 <= v <= 5 else None
    except ValueError:
        return None


def clean_count(val) -> int | None:
    if pd.isna(val):
        return None
    s = re.sub(r"[^0-9]", "", str(val))
    return int(s) if s else None


def extract_brand(name: str) -> str:
    """Heuristic: first word of product name is usually the brand."""
    if not name:
        return ""
    return str(name).split()[0]


def split_category(cat: str):
    """Split 'Computers&Accessories|Cables|USB' into main + sub."""
    if not cat:
        return "", ""
    parts = str(cat).replace("&", " & ").split("|")
    main = parts[0].strip() if parts else ""
    sub  = parts[1].strip() if len(parts) > 1 else ""
    return main, sub


# ── Ingestor functions — one per dataset ──────────────────────────────────────

def ingest_amazon_sales(conn: sqlite3.Connection):
    """Dataset: karkavelrajaj/amazon-sales-dataset  (1.4k rows, India, has reviews)"""
    csv_path = DATASETS_DIR / "amazon_sales" / "amazon.csv"
    if not csv_path.exists():
        log.warning(f"Not found: {csv_path} — skipping amazon_sales")
        return 0, 0

    log.info(f"Ingesting {csv_path} ...")
    df = pd.read_csv(csv_path, dtype=str)
    log.info(f"  Rows: {len(df)}, Columns: {list(df.columns)}")

    products_added = 0
    reviews_added  = 0
    cur = conn.cursor()

    for _, row in df.iterrows():
        asin     = str(row.get("product_id", "")).strip()
        name     = str(row.get("product_name", "")).strip()
        if not name or not asin:
            continue

        cat, sub = split_category(row.get("category", ""))
        disc     = clean_price(row.get("discounted_price"))
        actual   = clean_price(row.get("actual_price"))
        pct      = clean_pct(row.get("discount_percentage"))
        rating   = clean_rating(row.get("rating"))
        rcount   = clean_count(row.get("rating_count"))
        desc     = str(row.get("about_product", "")).strip() or None
        img      = str(row.get("img_link", "")).strip() or None
        url      = str(row.get("product_link", "")).strip() or None

        cur.execute("""
            INSERT INTO products
              (source, source_id, name, brand, category, sub_category,
               description, actual_price, discounted_price, currency,
               discount_pct, rating, rating_count, image_url, product_url, store)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, ("amazon_sales", asin, name, extract_brand(name), cat, sub,
              desc, actual, disc, "INR", pct, rating, rcount, img, url, "amazon"))

        product_db_id = cur.lastrowid
        products_added += 1

        # Ingest reviews for this product
        review_body  = str(row.get("review_content", "")).strip()
        review_title = str(row.get("review_title", "")).strip()
        reviewer     = str(row.get("user_name", "")).split(",")[0].strip()
        if review_body and review_body != "nan":
            cur.execute("""
                INSERT INTO reviews (product_id, reviewer, title, body)
                VALUES (?,?,?,?)
            """, (product_db_id, reviewer or None, review_title or None, review_body))
            reviews_added += 1

    conn.commit()
    log.info(f"  amazon_sales: {products_added} products, {reviews_added} reviews")
    return products_added, reviews_added


def ingest_amazon_products_2023(conn: sqlite3.Connection):
    """Dataset: lokeshparab/amazon-products-dataset (300k rows split by category)"""
    base = DATASETS_DIR / "amazon_products_2023"
    if not base.exists():
        log.warning(f"Not found: {base} — skipping amazon_products_2023")
        return 0, 0

    # This dataset has multiple CSVs, one per category
    csv_files = list(base.glob("*.csv"))
    if not csv_files:
        log.warning(f"No CSV files in {base}")
        return 0, 0

    log.info(f"Ingesting {len(csv_files)} category files from {base} ...")
    cur = conn.cursor()
    total = 0

    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except Exception as e:
            log.warning(f"  Could not read {csv_path.name}: {e}")
            continue

        # Detect column names (vary slightly between files)
        cols = {c.lower().strip(): c for c in df.columns}
        name_col  = cols.get("name") or cols.get("product_name") or cols.get("title")
        price_col = cols.get("selling_price") or cols.get("discounted_price") or cols.get("price")
        mrp_col   = cols.get("original_price") or cols.get("actual_price") or cols.get("mrp")
        rat_col   = cols.get("ratings") or cols.get("rating")
        rcnt_col  = cols.get("no_of_ratings") or cols.get("rating_count") or cols.get("num_ratings")
        img_col   = cols.get("image") or cols.get("img_link") or cols.get("image_url")
        url_col   = cols.get("link") or cols.get("product_link") or cols.get("url")

        if not name_col:
            continue

        cat_name = csv_path.stem.replace("_", " ").title()
        added = 0

        for _, row in df.iterrows():
            name = str(row.get(name_col, "")).strip()
            if not name or name == "nan":
                continue

            disc   = clean_price(row.get(price_col)) if price_col else None
            actual = clean_price(row.get(mrp_col)) if mrp_col else None
            rating = clean_rating(row.get(rat_col)) if rat_col else None
            rcount = clean_count(row.get(rcnt_col)) if rcnt_col else None
            img    = str(row.get(img_col, "")).strip() if img_col else None
            url    = str(row.get(url_col, "")).strip() if url_col else None

            cur.execute("""
                INSERT INTO products
                  (source, name, brand, category, actual_price,
                   discounted_price, currency, rating, rating_count,
                   image_url, product_url, store)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("amazon_2023", name, extract_brand(name), cat_name,
                  actual, disc, "INR", rating, rcount,
                  img if img and img != "nan" else None,
                  url if url and url != "nan" else None,
                  "amazon"))
            added += 1

        total += added

    conn.commit()
    log.info(f"  amazon_products_2023: {total} products")
    return total, 0


def ingest_amazon_1_4m(conn: sqlite3.Connection):
    """Dataset: asaniczka/amazon-products-dataset-2023-1-4m-products"""
    base = DATASETS_DIR / "amazon_1_4m"
    csv_path = base / "amazon_products.csv"
    if not csv_path.exists():
        alternate_names = [
            base / "amazon_products_2023.csv",
            base / "products.csv",
        ]
        for candidate in alternate_names:
            if candidate.exists():
                csv_path = candidate
                break
    if not csv_path.exists():
        candidates = sorted(
            base.glob("*.csv"),
            key=lambda path: (path.name != "amazon_products.csv", path.stat().st_size * -1),
        )
        if not candidates:
            log.warning(f"Not found: amazon_1_4m CSV — skipping")
            return 0, 0
        csv_path = candidates[0]

    log.info(f"Ingesting {csv_path} (large file, this may take a minute) ...")
    cur = conn.cursor()
    total = 0
    chunk_size = 10000

    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=chunk_size):
        rows = []
        for _, row in chunk.iterrows():
            asin  = str(row.get("asin", "")).strip()
            name  = str(row.get("title", "")).strip()
            if not name or name == "nan":
                continue

            cat, sub = split_category(row.get("category_name", ""))
            price    = clean_price(row.get("price"))
            rating   = clean_rating(row.get("stars"))
            rcount   = clean_count(row.get("reviews"))
            img      = str(row.get("imgUrl", "")).strip() or None
            url      = str(row.get("productURL", "")).strip() or None

            rows.append((
                "amazon_1_4m", asin or None, name, extract_brand(name),
                cat, sub, None, None, price, "USD",
                None, rating, rcount,
                img if img and img != "nan" else None,
                url if url and url != "nan" else None,
                "amazon",
            ))

        cur.executemany("""
            INSERT INTO products
              (source, source_id, name, brand, category, sub_category,
               description, actual_price, discounted_price, currency,
               discount_pct, rating, rating_count, image_url, product_url, store)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        total += len(rows)

    conn.commit()
    log.info(f"  amazon_1_4m: {total} products")
    return total, 0


def ingest_flipkart_products(conn: sqlite3.Connection):
    """Dataset: PromptCloudHQ/flipkart-products (20k products with specs)"""
    csv_path = DATASETS_DIR / "flipkart_products" / "flipkart_com-ecommerce_sample.csv"
    if not csv_path.exists():
        candidates = list((DATASETS_DIR / "flipkart_products").glob("*.csv"))
        if not candidates:
            log.warning("Not found: flipkart_products CSV — skipping")
            return 0, 0
        csv_path = candidates[0]

    log.info(f"Ingesting {csv_path} ...")
    cur = conn.cursor()
    total = 0

    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        log.warning(f"Could not read flipkart_products: {e}")
        return 0, 0

    log.info(f"  Rows: {len(df)}, Columns: {list(df.columns[:10])}")
    cols = {c.lower().strip(): c for c in df.columns}

    name_col  = cols.get("product_name") or cols.get("name")
    price_col = cols.get("discounted_price") or cols.get("retail_price") or cols.get("price")
    mrp_col   = cols.get("retail_price") or cols.get("mrp")
    cat_col   = cols.get("product_category_tree") or cols.get("category")
    desc_col  = cols.get("description") or cols.get("product_description")
    img_col   = cols.get("image") or cols.get("image_url")
    url_col   = cols.get("product_url") or cols.get("url")
    pid_col   = cols.get("pid") or cols.get("product_id")

    for _, row in df.iterrows():
        name = str(row.get(name_col, "") if name_col else "").strip()
        if not name or name == "nan":
            continue

        raw_cat = str(row.get(cat_col, "") if cat_col else "").strip()
        # Flipkart categories look like: ["Electronics >> Headphones >> ..."]
        raw_cat = raw_cat.strip('"[]').replace(">>", "|").replace('"', "")
        cat, sub = split_category(raw_cat)

        disc   = clean_price(row.get(price_col) if price_col else None)
        actual = clean_price(row.get(mrp_col) if mrp_col else None)
        desc   = str(row.get(desc_col, "") if desc_col else "").strip() or None
        img    = str(row.get(img_col, "") if img_col else "").strip() or None
        url    = str(row.get(url_col, "") if url_col else "").strip() or None
        pid    = str(row.get(pid_col, "") if pid_col else "").strip() or None

        cur.execute("""
            INSERT INTO products
              (source, source_id, name, brand, category, sub_category,
               description, actual_price, discounted_price, currency,
               image_url, product_url, store)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, ("flipkart", pid, name, extract_brand(name), cat, sub,
              desc if desc != "nan" else None,
              actual, disc, "INR",
              img if img and img != "nan" else None,
              url if url and url != "nan" else None,
              "flipkart"))
        total += 1

    conn.commit()
    log.info(f"  flipkart_products: {total} products")
    return total, 0


def ingest_flipkart_reviews(conn: sqlite3.Connection):
    """Dataset: niraliivaghani/flipkart-dataset (363k reviews with sentiment)"""
    base = DATASETS_DIR / "flipkart_reviews"
    if not base.exists():
        log.warning("Not found: flipkart_reviews — skipping")
        return 0, 0

    candidates = list(base.glob("*.csv"))
    if not candidates:
        log.warning(f"No CSV in {base} — skipping")
        return 0, 0

    cur = conn.cursor()
    total = 0

    for csv_path in candidates:
        try:
            df = pd.read_csv(csv_path, dtype=str, nrows=100000)  # cap at 100k for memory
        except Exception as e:
            try:
                df = pd.read_csv(
                    csv_path,
                    dtype=str,
                    nrows=100000,
                    encoding="latin-1",
                )
            except Exception as inner_exc:
                log.warning(f"Could not read {csv_path.name}: {inner_exc}")
                continue

        cols = {c.lower().strip(): c for c in df.columns}
        prod_col   = cols.get("product_name") or cols.get("product") or cols.get("item_name")
        body_col   = cols.get("review") or cols.get("review_text") or cols.get("comment")
        rating_col = cols.get("rating") or cols.get("star_rating")
        sent_col   = cols.get("sentiment") or cols.get("label")

        if not body_col:
            continue

        for _, row in df.iterrows():
            body = str(row.get(body_col, "")).strip()
            if not body or body == "nan":
                continue

            prod_name = str(row.get(prod_col, "") if prod_col else "").strip()
            rating    = clean_rating(row.get(rating_col) if rating_col else None)
            sentiment = str(row.get(sent_col, "") if sent_col else "").strip() or None

            # Try to find a matching product in our products table
            product_id = None
            if prod_name and prod_name != "nan":
                cur.execute(
                    "SELECT id FROM products WHERE name LIKE ? AND store='flipkart' LIMIT 1",
                    (f"%{prod_name[:40]}%",)
                )
                match = cur.fetchone()
                if match:
                    product_id = match[0]

            if product_id:
                cur.execute("""
                    INSERT INTO reviews (product_id, body, rating, sentiment)
                    VALUES (?,?,?,?)
                """, (product_id, body, rating, sentiment))
                total += 1

    conn.commit()
    log.info(f"  flipkart_reviews: {total} reviews matched and ingested")
    return 0, total


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Scoutr v2 — Product Database Ingestion")
    log.info("=" * 60)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Create schema
    conn.execute(CREATE_PRODUCTS)
    conn.execute(CREATE_REVIEWS)
    for idx in CREATE_INDEXES:
        conn.execute(idx)
    conn.commit()
    log.info(f"Database ready at {DB_PATH}")

    total_products = 0
    total_reviews  = 0

    # Run all ingestors in priority order
    ingestors = [
        ("amazon_sales",          ingest_amazon_sales),
        ("amazon_products_2023",  ingest_amazon_products_2023),
        ("amazon_1_4m",           ingest_amazon_1_4m),
        ("flipkart_products",     ingest_flipkart_products),
        ("flipkart_reviews",      ingest_flipkart_reviews),
    ]

    for name, fn in ingestors:
        log.info(f"\n--- {name} ---")
        p, r = fn(conn)
        total_products += p
        total_reviews  += r

    # Final stats
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    p_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM reviews")
    r_count = cur.fetchone()[0]
    cur.execute("SELECT store, COUNT(*) FROM products GROUP BY store")
    stores = cur.fetchall()
    cur.execute("SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10")
    top_cats = cur.fetchall()

    conn.close()

    log.info("\n" + "=" * 60)
    log.info(f"DONE — {p_count:,} products, {r_count:,} reviews in {DB_PATH}")
    log.info("Products by store:")
    for store, count in stores:
        log.info(f"  {store or 'unknown'}: {count:,}")
    log.info("Top 10 categories:")
    for cat, count in top_cats:
        log.info(f"  {cat or 'unknown'}: {count:,}")
    log.info("\nNext step: python scripts/build_embeddings.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
