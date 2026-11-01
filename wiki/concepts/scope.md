---
title: scope
description: Pallet concepts scope.
---
# Scope

A scope focuses a search on one provider. `split_scope()` in [host.py](../../src/host.py) removes recognized prefixes and returns a provider name and bare query; `Provider.wants()` also uses manifest routing hints. The [search flow](../flows/search.md) returns the scope and bare text so the [shell](../modules/shell.md) can rank against the matched query. User-facing prefixes are listed in [Pallet](../../README.md).
