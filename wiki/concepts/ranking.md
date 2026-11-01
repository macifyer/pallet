---
title: ranking
description: Pallet concepts ranking.
---
# Ranking

`rank()` in [Fuzzy.js](../../shell/Fuzzy.js) orders matching results by exact, prefix, word, substring and subsequence tiers, blending advisory score and recency within tiers. Fallback rows sort last; file intent changes how file results compete with commands. `History` in [host.py](../../src/host.py) supplies recency. See [search](../flows/search.md) and [change ranking](../guides/change-ranking.md).
