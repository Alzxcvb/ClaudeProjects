"""Tests for inventory.py. Run: python3 test_inventory.py (also pytest-compatible)."""

from inventory import Catalog


def test_add_and_read_back():
    c = Catalog()
    c.add_item("hammer", 5)
    assert c.quantity_of("hammer") == 5


def test_explicit_tags_are_kept():
    c = Catalog()
    c.add_item("saw", 2, tags=["tools"])
    assert "tools" in c.tags_for("saw")
    assert "in-stock" in c.tags_for("saw")


def test_default_tags_do_not_leak_between_items():
    c = Catalog()
    c.add_item("hammer", 5)
    c.add_item("wrench", 3)
    assert c.tags_for("hammer") == ["in-stock"]
    assert c.tags_for("wrench") == ["in-stock"]


def test_low_stock_includes_items_at_threshold():
    c = Catalog()
    c.add_item("nails", 3)
    assert "nails" in c.low_stock(3)


def test_low_stock_excludes_items_above_threshold():
    c = Catalog()
    c.add_item("screws", 5)
    assert "screws" not in c.low_stock(3)


if __name__ == "__main__":
    import sys
    import traceback

    failures = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
