---
title: Wiki Log
description: Append-only audit trail of wiki generation and refresh runs.
---

# Wiki Log

Append-only audit trail. Add one dated entry per generation or refresh run, recording the profile, the `source_commit` it was anchored to, and the coverage. The codebase-wiki skill describes the entry shape.

## 2026-11-01: generate

- Profile: internal/standard
- source_commit: 6805a59
- Coverage: architecture, shell, host, ten providers, search and action flows, concepts and guides.
- Pages: [Overview](./OVERVIEW.md), [architecture/system](./architecture/system.md), [modules/shell](./modules/shell.md), [modules/host](./modules/host.md), [modules/apps](./modules/apps.md), [modules/defaults](./modules/defaults.md), [modules/files](./modules/files.md), [modules/menus](./modules/menus.md), [modules/obsidian](./modules/obsidian.md), [modules/omarchy](./modules/omarchy.md), [modules/plugins](./modules/plugins.md), [modules/run](./modules/run.md), [modules/system](./modules/system.md), [modules/windows](./modules/windows.md), [flows/search](./flows/search.md), [flows/execute](./flows/execute.md), [concepts/provider](./concepts/provider.md), [concepts/scope](./concepts/scope.md), [concepts/ranking](./concepts/ranking.md), [concepts/confirmation](./concepts/confirmation.md), [guides/add-provider](./guides/add-provider.md), [guides/change-ranking](./guides/change-ranking.md).

## 2026-11-01: refresh

- Profile: internal/standard
- source_commit: c8e65d3 (was 6805a59)
- Coverage: added plugin shell, provider host, and provider contract pages; summon flow; result, action, and frecency concepts. Linked them from the overview, system page, and search and execute flows.
- Pages: [Overview](./OVERVIEW.md), [Plugin shell](./architecture/plugin-shell.md), [Provider host](./architecture/provider-host.md), [Provider contract](./architecture/provider-contract.md), [System](./architecture/system.md), [Summon](./flows/summon.md), [Search](./flows/search.md), [Execute](./flows/execute.md), [Result](./concepts/result.md), [Action](./concepts/action.md), [Frecency](./concepts/frecency.md).

