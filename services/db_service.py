"""
services/db_service.py

Provides product retrieval from SQLite with an optional FAISS semantic layer.
The service remains usable in SQL-only mode if the local embedding model or
index files are unavailable.
"""

import json
import logging
import sqlite3
from pathlib import Path

import numpy as np

from config import settings

log = logging.getLogger(__name__)

DB_PATH = Path("data/products.db")
INDEX_PATH = Path("data/faiss_index.bin")
IDS_PATH = Path("data/faiss_ids.json")
MODEL_DIR = Path(settings.EMBEDDING_MODEL_DIR)

TIER_RANGES_INR = {
    "cost_effective": (0, 3000),
    "basic": (3000, 10000),
    "premium": (10000, 30000),
    "lavish": (30000, None),
}

TIER_RANGES_USD = {
    "cost_effective": (0, 50),
    "basic": (50, 150),
    "premium": (150, 400),
    "lavish": (400, None),
}


class ProductDB:
    """Singleton product database service with optional semantic search."""

    _instance = None

    @classmethod
    def get(cls) -> "ProductDB":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._db_path = DB_PATH
        self._index = None
        self._ids: list[int] | None = None
        self._model = None
        self._ready = False
        self._semantic_ready = False
        self._load()

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def semantic_ready(self) -> bool:
        return self._semantic_ready

    def _load(self) -> None:
        if not self._db_path.exists():
            log.warning(
                "products.db not found. Run scripts/ingest_products.py first. "
                "Falling back to AI-only recommendations."
            )
            return

        self._ready = True
        log.info("ProductDB SQL layer ready")

        if not INDEX_PATH.exists() or not IDS_PATH.exists():
            log.warning("FAISS index files are missing. ProductDB will run in SQL-only mode.")
            return

        if not MODEL_DIR.exists():
            log.warning(
                "Local embedding model not found at %s. ProductDB will run in SQL-only mode.",
                MODEL_DIR,
            )
            return

        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            log.info("Loading FAISS index from %s", INDEX_PATH)
            self._index = faiss.read_index(str(INDEX_PATH))
            self._ids = json.loads(IDS_PATH.read_text(encoding="utf-8"))

            log.info("Loading local embedding model from %s", MODEL_DIR)
            self._model = SentenceTransformer(str(MODEL_DIR), local_files_only=True)

            self._semantic_ready = True
            log.info("ProductDB semantic layer ready - %s vectors", f"{self._index.ntotal:,}")
        except ImportError:
            log.warning(
                "sentence-transformers or faiss-cpu not installed. "
                "ProductDB will run in SQL-only mode."
            )
        except Exception as exc:
            log.warning("ProductDB semantic load failed: %s. Using SQL-only mode.", exc)

    def search(
        self,
        query: str,
        category_hint: str | None = None,
        store: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_rating: float | None = 3.5,
        top_k: int = 20,
    ) -> list[dict]:
        """Hybrid search with a safe SQL-only fallback."""
        if not self._ready:
            return []

        sql_ids = self._sql_search(
            category_hint=category_hint,
            store=store,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            top_k=top_k * 5,
        )

        semantic_ids: list[int] = []
        if self._semantic_ready:
            semantic_ids = self._semantic_search(query, top_k=top_k * 3)

        if not semantic_ids:
            return self._fetch_products(sql_ids[:top_k])

        semantic_rank = {pid: rank for rank, pid in enumerate(semantic_ids)}
        sql_set = set(sql_ids)

        scored: list[tuple[int, int]] = []
        all_ids = set(semantic_ids) | sql_set
        for pid in all_ids:
            sem_score = semantic_rank.get(pid, len(semantic_ids))
            in_sql = 1 if pid in sql_set else 0
            combined = sem_score - (in_sql * top_k * 2)
            scored.append((combined, pid))

        scored.sort()
        top_ids = [pid for _, pid in scored[:top_k]]
        return self._fetch_products(top_ids)

    def search_for_tiers(
        self,
        query: str,
        category_hint: str | None = None,
        store: str | None = None,
    ) -> dict[str, list[dict]]:
        """Returns 3 products per tier using semantic+SQL or SQL-only search."""
        ranges = TIER_RANGES_USD if store == "amazon" and not category_hint else TIER_RANGES_INR
        results: dict[str, list[dict]] = {}

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

    def _semantic_search(self, query: str, top_k: int) -> list[int]:
        if not self._semantic_ready or self._model is None or self._index is None or self._ids is None:
            return []

        try:
            vector = self._model.encode([query], normalize_embeddings=True).astype(np.float32)
            _, indices = self._index.search(vector, top_k)
            return [self._ids[i] for i in indices[0] if i >= 0]
        except Exception as exc:
            log.warning("Semantic search failed: %s", exc)
            return []

    def _sql_search(
        self,
        category_hint: str | None = None,
        store: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_rating: float | None = None,
        top_k: int = 100,
    ) -> list[int]:
        try:
            conn = sqlite3.connect(self._db_path)
            cur = conn.cursor()

            conditions = ["is_available = 1"]
            params: list[object] = []

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

            query = f"""
                SELECT id
                FROM products
                WHERE {' AND '.join(conditions)}
                ORDER BY rating DESC, rating_count DESC
                LIMIT ?
            """
            params.append(top_k)
            cur.execute(query, params)
            ids = [row[0] for row in cur.fetchall()]
            conn.close()
            return ids
        except Exception as exc:
            log.warning("SQL search failed: %s", exc)
            return []

    def _fetch_products(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            placeholders = ",".join("?" * len(ids))
            cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", ids)
            rows = [dict(row) for row in cur.fetchall()]
            conn.close()

            order = {pid: index for index, pid in enumerate(ids)}
            rows.sort(key=lambda row: order.get(row["id"], len(ids)))
            return rows
        except Exception as exc:
            log.warning("Fetch products failed: %s", exc)
            return []

    def get_reviews(self, product_id: int, limit: int = 3) -> list[dict]:
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT title, body, rating, sentiment
                FROM reviews
                WHERE product_id = ?
                ORDER BY rating DESC
                LIMIT ?
                """,
                (product_id, limit),
            )
            reviews = [dict(row) for row in cur.fetchall()]
            conn.close()
            return reviews
        except Exception as exc:
            log.warning("Get reviews failed: %s", exc)
            return []


def get_db() -> ProductDB:
    """Convenience singleton accessor."""
    return ProductDB.get()
