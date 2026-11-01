---
title: search
description: Pallet flows search.
---
# Search and streaming

```mermaid
sequenceDiagram
  participant U as User
  participant S as Shell
  participant H as Host
  participant P as Providers
  U->>S: Type query
  S->>H: search with query id
  H->>P: scoped or mixed search
  P-->>H: partial or complete results
  H-->>S: cumulative snapshot
  S->>S: reject stale ids and rank rows
```

Opening the palette is [summon](./summon.md). [PaletteWindow.qml](../../shell/PaletteWindow.qml) debounces input and cancels stale searches. [ProviderBridge.qml](../../shell/ProviderBridge.qml) assigns ids and accepts current responses. `Host.on_search()` and `Host._merge()` in [host.py](../../src/host.py) route the [scope](../concepts/scope.md), merge [provider](../concepts/provider.md) [results](../concepts/result.md), stamp [frecency](../concepts/frecency.md), and report pending or unresolved providers. The [shell](../modules/shell.md) applies [ranking](../concepts/ranking.md) to each snapshot. Routing rules are on the [provider host](../architecture/provider-host.md) page.
