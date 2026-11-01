---
title: change ranking
description: Pallet guides change-ranking.
---
# Change search or ranking

1. For provider routing or streaming, inspect `Host.on_search()` and `Host._merge()` in [host.py](../../src/host.py), and the [search flow](../flows/search.md).
2. For result ordering, change `rank()` or its helpers in [Fuzzy.js](../../shell/Fuzzy.js); preserve the intended [ranking](../concepts/ranking.md) tiers and fallback behavior.
3. Add a behavioral case to [ranking.cjs](../../tests/ranking.cjs), and run `node tests/ranking.cjs` alongside relevant host tests. The [shell](../modules/shell.md) also handles stale queries and streaming selection, so check those interactions when changing result identity.
