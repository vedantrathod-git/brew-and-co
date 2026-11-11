import sys
import time
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import Response
from app.db.session import SessionLocal
from app.api.public import get_public_menu, invalidate_public_menu_cache

def test_public_menu_caching_and_speed():
    print("=" * 70)
    print(" Testing Public Menu Server-Side Cache & Latency")
    print("=" * 70)

    invalidate_public_menu_cache()
    db = SessionLocal()

    try:
        # 1. First call: Cache MISS (queries DB)
        resp1 = Response()
        t0 = time.perf_counter()
        data1 = get_public_menu(category_id=None, search=None, response=resp1, db=db)
        t1 = time.perf_counter()
        dur1_ms = (t1 - t0) * 1000

        assert len(data1.items) == 70, f"Expected 70 items, got {len(data1.items)}"
        assert len(data1.categories) == 9, f"Expected 9 categories, got {len(data1.categories)}"
        assert resp1.headers.get("X-Cache") == "MISS", f"Expected MISS, got {resp1.headers.get('X-Cache')}"
        assert "public, max-age=60" in resp1.headers.get("Cache-Control", ""), "Missing Cache-Control header"
        print(f"  ✓ First request (Cache MISS - Neon DB Query): {dur1_ms:.2f} ms | Items: {len(data1.items)} | Categories: {len(data1.categories)}")

        # 2. Second call: Cache HIT (in-process memory)
        resp2 = Response()
        t2 = time.perf_counter()
        data2 = get_public_menu(category_id=None, search=None, response=resp2, db=db)
        t3 = time.perf_counter()
        dur2_ms = (t3 - t2) * 1000

        assert resp2.headers.get("X-Cache") == "HIT", f"Expected HIT, got {resp2.headers.get('X-Cache')}"
        assert len(data2.items) == 70
        assert data1.items == data2.items
        print(f"  ✓ Second request (Cache HIT - In-Memory): {dur2_ms:.3f} ms ({(dur1_ms / max(dur2_ms, 0.001)):.1f}x speedup!)")

        # 3. Third call: Cache invalidation
        invalidate_public_menu_cache()
        resp3 = Response()
        data3 = get_public_menu(category_id=None, search=None, response=resp3, db=db)
        assert resp3.headers.get("X-Cache") == "MISS", "Expected MISS after invalidation"
        print("  ✓ Cache invalidation successfully resets cache state to MISS")

        # 4. Parametric filter bypasses base cache correctly
        resp_filtered = Response()
        data_filtered = get_public_menu(category_id=1, search=None, response=resp_filtered, db=db)
        assert all(item.category_id == 1 for item in data_filtered.items)
        print("  ✓ Parametric category filtering works accurately")

        print("\n" + "=" * 70)
        print(" ALL PUBLIC MENU CACHE & LATENCY TESTS PASSED!")
        print("=" * 70)
    finally:
        db.close()

if __name__ == "__main__":
    test_public_menu_caching_and_speed()
