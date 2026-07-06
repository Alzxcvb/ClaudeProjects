# Task: Fix the catalog bugs

You maintain a small inventory module, `inventory.py`. Two bug reports came in from users:

1. "Items are picking up each other's tags. I added a hammer with no tags, then a wrench with no tags, and now the hammer shows multiple `in-stock` tags."
2. "The low-stock report misses items sitting exactly at the threshold. An item with quantity 3 doesn't show up in `low_stock(3)`, but the docs say it should."

There is a test file, `test_inventory.py`. Run it with:

```bash
python3 test_inventory.py
```

Fix both bugs. Do not change the public interface (method names and signatures other than default values may not change), and do not break the passing tests.
