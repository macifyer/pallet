---
title: provider
description: Pallet concepts provider.
---
# Provider

A provider is a subprocess that receives and returns newline-delimited JSON, as described in [Provider protocol](../../docs/PROVIDERS.md). The [host](../modules/host.md) discovers provider manifests and manages their processes in [host.py](../../src/host.py). Providers produce results for the [search flow](../flows/search.md); custom actions return to their owning provider in the [execution flow](../flows/execute.md). See [adding a provider](../guides/add-provider.md).
