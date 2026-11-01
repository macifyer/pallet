---
title: system
description: Pallet architecture system.
---
# System architecture

Pallet is an Omarchy command palette with a Quickshell frontend, a Python host and provider subprocesses. The plugin entry points are declared in [manifest.json](../../manifest.json); the overlay instantiates the palette in [PalletOverlay.qml](../../PalletOverlay.qml), and [Service.qml](../../Service.qml) manages the hotkey.

```mermaid
flowchart LR
  User --> Shell[QML shell]
  Shell -->|JSON lines| Host[Python host]
  Host -->|JSON lines| Providers[Provider processes]
  Providers --> Desktop[Desktop services and files]
  Host --> History[(History)]
```

The [shell](../modules/shell.md) starts the [host](../modules/host.md), which discovers [providers](../concepts/provider.md), routes searches and merges responses. See the [search flow](../flows/search.md) and [action flow](../flows/execute.md). The host keeps subprocess boundaries between UI and providers; the manifest-based protocol is documented in [Provider protocol](../../docs/PROVIDERS.md).
