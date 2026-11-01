---
title: Result
description: One provider row, its identity, and the fields the shell ranks.
---
# Result

## Definition

A result is one row a provider returns for a query. The host stamps `provider` on each object and may stamp `recent`. The shell drops rows that do not match the query and orders the rest.

## Why it matters

Selection follows a stable `id` while snapshots stream in. `Fuzzy.keyOf()` builds `provider`, a NUL, then `id` or `title`. `History.key()` uses the same shape, so a recorded choice lines up with the row that produced it.

## Where it lives

Providers build the objects. `Host._merge()` in [host.py](../../src/host.py) copies them into one list in provider-start order and emits that list on every snapshot. `rank()` in [Fuzzy.js](../../shell/Fuzzy.js) reads `title`, `keywords`, `subtitle`, `score`, `fallback`, `provider`, and `recent`. Display fields such as `icon`, `icons`, `fallbackIcon`, and `fallbackColor` are specified in the [provider protocol](../../docs/PROVIDERS.md).

## Related

[Provider](./provider.md), [ranking](./ranking.md), [frecency](./frecency.md), [search](../flows/search.md), [provider contract](../architecture/provider-contract.md).
