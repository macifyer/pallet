---
title: add provider
description: Pallet guides add-provider.
---
# Add a provider

1. Start with [provider.py](../../providers/_template/provider.py) and [manifest.json](../../providers/_template/manifest.json) in the template directory; create a new provider directory.
2. Implement search and the relevant cancellation, warm and custom execution messages described in [Provider protocol](../../docs/PROVIDERS.md). Return stable result IDs and declared actions.
3. Check discovery and routing in `discover_manifests()` and `split_scope()` in [host.py](../../src/host.py); add an explicit scope if needed.
4. Exercise search, cancellation and actions with tests following [test_host.py](../../tests/test_host.py), then run the checks in [Pallet](../../README.md).

The [provider concept](../concepts/provider.md) and [search flow](../flows/search.md) explain the boundary.
