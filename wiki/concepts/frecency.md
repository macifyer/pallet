---
title: Frecency
description: Decayed choice history that reorders rows inside a match tier.
---
# Frecency

## Definition

Frecency is a decayed count of how often a result was chosen. Choosing a row sends `op: record`. The host stores a weight and a timestamp, halves the weight across 14 days, and turns that weight into a `recent` value from 0 to 1.

## Why it matters

`recent` reorders rows only inside one match tier. A better tier still wins. Rows from the `run` provider are never stored. `PALLET_HISTORY=0` disables the store. The file is `$XDG_STATE_HOME/pallet/history.json`, or `~/.local/state/pallet/history.json` when that variable is unset. At most 400 keys are kept.

## Where it lives

`History.record()`, `History.score()`, and `History.annotate()` live in [host.py](../../src/host.py). `HISTORY_HALF_LIFE_S` is 14 days. `score()` divides the decayed weight by 5 and caps it at 1. `ProviderBridge.record()` in [ProviderBridge.qml](../../shell/ProviderBridge.qml) sends the provider, the result id, and the title before an action runs. `rank()` in [Fuzzy.js](../../shell/Fuzzy.js) adds `0.15 * recent` inside the current tier.

## Related

[Ranking](./ranking.md), [result](./result.md), [host](../modules/host.md), [search](../flows/search.md).
