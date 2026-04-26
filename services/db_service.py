"""
services/db_service.py
Provides fast product retrieval from SQLite using:
  1. SQL filtering — exact category, price range, store, rating filters
  2. FAISS semantic search — meaning-based similarity matching
  3. Hybrid merge — combines both for best results

This replaces the AI inventing products.
The AI now only writes explanations for real products from this database.
"""

import json
import sqlite3
import logging
import numpy as np
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH    = Path("data/products.db")
INDEX_PATH = Path("data/faiss_index.bin")
IDS_PATH   = Path("data/faiss_ids.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Tier price ranges ─────────────────────────────────────────────────────────
TIER_RANGES_INR = {
    "cost_effective": (0,    3000),
    "basic":          (3000, 10000),
    "premium":        (10000, 30000),
    "lavish":         (30000, None),
}

TIER_RANGES_USD = {
    "cost_effective": (0,   50),
    "basic":          (50,  150),
    "premium":        (150, 400),
    "lavish":         (400, None),
}


class ProductDB:
    """
    Singleton that loads the FAISS index and SQLite DB once at startup
    and serves product queries efficiently.
    """

    _instance = None

    @classmethod
    def get(cls) -> "ProductDB":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._model   = None
        self._index   = None
        self._ids     = None
        self._db_path = DB_PATH
        self._ready   = False
        self._load()

    def _load(self):
        if not DB_PATH.exists():
            log.warning(
                "products.db not found. Run scripts/ingest_products.py first. "
                "Falling back to AI-only recommendations."
            )
            return

        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            log.info("Loading FAISS index...")
            self._index = faiss.read_index(str(INDEX_PATH))
            with open(IDS_PATH) as f:
                self._ids = json.load(f)

            log.info(f"Loading embedding model: {EMBEDDING_MODEL} ...")
            self._model = SentenceTransformer(EMBEDDING_MODEL)

            self._ready = True
            log.info(f"ProductDB ready — {self._index.ntotal:,} vectors")

        except ImportError:
            log.warning(
                "sentence-transformers or faiss-cpu not installed. "
                "Add them to requirements.txt and re-deploy. "
                "Falling back to AI-only mode."
            )
        except Exception as e:
            log.warning(f"ProductDB load failed: {e}. Falling back to AI-only mode.")

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Core search ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        category_hint: str = None,
        store: str = None,
        min_price: float = None,
        max_price: float = None,
        min_rating: float = 3.5,
        top_k: int = 20,
    ) -> list[dict]:
        """
        Hybrid search: semantic FAISS + SQL filtering, results merged.
        Returns up to top_k product dicts sorted by relevance score.
        """
        if not self._ready:
            return []

        # Step 1: Semantic search — find top_k*3 candidates
        semantic_ids = self._semantic_search(query, top_k=top_k * 3)

        # Step 2: SQL filter candidates
        sql_ids = self._sql_search(
            category_hint=category_hint,
            store=store,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            top_k=top_k * 5,
        )

        # Step 3: Merge — prefer products appearing in both sets
        semantic_set = {pid: rank for rank, pid in enumerate(semantic_ids)}
        sql_set      = set(sql_ids)

        scored = []
        all_ids = set(semantic_ids) | sql_set
        for pid in all_ids:
            sem_score = semantic_set.get(pid, len(semantic_ids))  # lower = better
            in_sql    = 1 if pid in sql_set else 0
            # Combined score: appears in both → best rank
            combined  = sem_score - (in_sql * top_k * 2)
            scored.append((combined, pid))

        scored.sort()
        top_ids = [pid for _, pid in scored[:top_k]]

        if not top_ids:
            return []

        return self._fetch_products(top_ids)

    def search_for_tiers(self, query: str, category_hint: str = None, store: str = None) -> dict:
        """
        Returns 3 products per tier (cost_effective, basic, premium, lavish).
        Uses the appropriate price range for each tier.
        Falls back to semantic-only search if no price-matched products found.
        """
        results = {}

        # Determine currency from store
        ranges = TIER_RANGES_USD if store == "amazon" and not category_hint else TIER_RANGES_INR

        for tier, (lo, hi) in ranges.items():
            products = self.search(
                query=query,
                category_hint=category_hint,
                store=store,
                min_price=lo,
                max_price=hi,
                min_rating=3.5,
                top_k=6,
            )

            # Fallback: if price-filtered search returns < 3, drop the price filter
            if len(products) < 3:
                products = self.search(
                    query=query,
                    category_hint=category_hint,
                    store=store,
                    min_price=None,
                    max_price=None,
                    min_rating=3.0,
                    top_k=6,
                )

            results[tier] = products[:3]

        return results

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _semantic_search(self, query: str, top_k: int) -> list[int]:
        """Returns list of product DB IDs ranked by semantic similarity."""
        try:
            vec = self._model.encode([query], normalize_embeddings=True).astype(np.float32)
            _, indices = self._index.search(vec, top_k)
            return [self._ids[i] for i in indices[0] if i >= 0]
        except Exception as e:
            log.warning(f"Semantic search failed: {e}")
            return []

    def _sql_search(
        self,
        category_hint: str = None,
        store: str = None,
        min_price: float = None,
        max_price: float = None,
        min_rating: float = None,
        top_k: int = 100,
    ) -> list[int]:
        """Returns list of product DB IDs matching SQL filters."""
        try:
            conn = sqlite3.connect(self._db_path)
            cur  = conn.cursor()

            conditions = ["is_available = 1"]
            params = []

            if category_hint:
                conditions.append("(category LIKE ? OR sub_category LIKE ? OR name LIKE ?)")
                like = f"%{category_hint}%"
                params.extend([like, like, like])

            if store:
                conditions.append("store = ?")
                params.append(store)

            if min_price is not None:
                conditions.append("discounted_price >= ?")
                params.append(min_price)

            if max_price is not None:
                conditions.append("discounted_price <= ?")
                params.append(max_price)

            if min_rating is not None:
                conditions.append("(rating >= ? OR rating IS NULL)")
                params.append(min_rating)

            where = " AND ".join(conditions)
            query = f"""
                SELECT id FROM products
                WHERE {where}
                ORDER BY rating DESC, rating_count DESC
                LIMIT ?
            """
            params.append(top_k)
            cur.execute(query, params)
            ids = [row[0] for row in cur.fetchall()]
            conn.close()
            return ids
        except Exception as e:
            log.warning(f"SQL search failed: {e}")
            return []

    def _fetch_products(self, ids: list[int]) -> list[dict]:
        """Fetches full product rows for a list of IDs."""
        if not ids:
            return []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur  = conn.cursor()
            placeholders = ",".join("?" * len(ids))
            cur.execute(
                f"SELECT * FROM products WHERE id IN ({placeholders})",
                ids,
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            # Restore original order
            id_order = {pid: i for i, pid in enumerate(ids)}
            rows.sort(key=lambda r: id_order.get(r["id"], 999))
            return rows
        except Exception as e:
            log.warning(f"Fetch products failed: {e}")
            return []

    def get_reviews(self, product_id: int, limit: int = 3) -> list[dict]:
        """Returns top reviews for a product, ordered by rating."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur  = conn.cursor()
            cur.execute("""
                SELECT title, body, rating, sentiment
                FROM reviews
                WHERE product_id = ?
                ORDER BY rating DESC
                LIMIT ?
            """, (product_id, limit))
            reviews = [dict(r) for r in cur.fetchall()]
            conn.close()
            return reviews
        except Exception as e:
            log.warning(f"Get reviews failed: {e}")
            return []


# Convenience singleton accessor
def get_db() -> ProductDB:
    return ProductDB.get()
