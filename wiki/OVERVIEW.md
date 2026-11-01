---
title: Pallet codebase wiki
description: Architecture, modules, flows and guides for Pallet.
profile: internal/standard
source_commit: 6805a5924a9d4b9ebbceaea497d843786e09e1c5
tags:
  - wiki
  - overview
---
# Pallet wiki

Pallet is a keyboard-driven command palette for Omarchy on Quickshell. The [project README](../README.md) describes installation and user-facing scopes. The plugin entry points are declared in [manifest.json](../manifest.json).

## Architecture at a glance

```mermaid
flowchart LR
  User --> Shell[QML shell]
  Shell --> Host[Python host]
  Host --> Providers[Provider processes]
  Providers --> Desktop[Desktop services]
  Host --> History[(History)]
```

The [system architecture](./architecture/system.md) explains these boundaries; the [search flow](./flows/search.md) and [action flow](./flows/execute.md) follow the main interactions.

## Navigation

- **Architecture:** [System](./architecture/system.md)
- **Modules:** [shell](./modules/shell.md) · [host](./modules/host.md) · [apps](./modules/apps.md) · [defaults](./modules/defaults.md) · [files](./modules/files.md) · [menus](./modules/menus.md) · [obsidian](./modules/obsidian.md) · [omarchy](./modules/omarchy.md) · [plugins](./modules/plugins.md) · [run](./modules/run.md) · [system](./modules/system.md) · [windows](./modules/windows.md)
- **Flows:** [search](./flows/search.md) · [execute](./flows/execute.md)
- **Concepts:** [provider](./concepts/provider.md) · [scope](./concepts/scope.md) · [ranking](./concepts/ranking.md) · [confirmation](./concepts/confirmation.md)
- **Guides:** [add-provider](./guides/add-provider.md) · [change-ranking](./guides/change-ranking.md)
- **Existing reference:** [Provider protocol](../docs/PROVIDERS.md), [Pallet README](../README.md)
