# Provider protocol

A provider is a subprocess speaking newline-delimited JSON over stdio. It is never a QML plugin, never executes arbitrary shell commands from search text, and everything it runs is declared in its manifest and visible to the user.

## Manifest

```json
{"name": "apps", "exec": ["python3", "providers/apps/provider.py"], "capabilities": ["search"]}
```

Optional routing hints:

- `minQuery` — skip unscoped queries shorter than this many characters
  (files and run use 3, menus and defaults 2). Scoped queries always reach the
  provider, even when empty.
- `scopedOnly: true` — only answer when the query is explicitly scoped.

## Messages

Host to provider: `{"id":"q1","op":"search","query":"fire","scope":""}` · `{"id":"q2","op":"cancel","target":"q1"}` · `{"id":"a1","op":"execute","action":{...}}` · `{"id":"","op":"warm"}`.

Provider to host: `{"id":"q1","results":[...]}` · `{"id":"q1","results":[...],"partial":true}` · `{"id":"q1","cancelled":true}` · `{"id":"a1","executed":false,"error":"why"}`.

- `query` is the bare text with any scope prefix removed; `scope` is the
  provider name when the user scoped the query (`f:`, `web:`, ...), else `""`.
- `partial: true` streams what is ready now; send the complete list later
  under the same id without `partial`. Each reply replaces the provider's
  earlier rows for that query.
- `warm` is sent when the overlay opens: pre-load caches, reply nothing.
  Unknown ops must be ignored.
- `executed: false` with an `error` string is shown to the user (footer and
  an `omarchy-notification-send` notification).

The host tags merged results with their provider name; custom actions route only back to that owning provider.
It streams cumulative merged snapshots to the client with `final`, `pending`
(still answering), `failed` (dead/unavailable), `unresolved` (on the final
snapshot: providers that did not answer by the deadline) plus `scope` and
`bare`. Rows arriving shortly after the deadline are still merged in.

Client to host (besides `search`/`cancel`/`execute`/`warm`):
`{"id":"l1","op":"launch","argv":[...]}` or `{"id":"l1","op":"launch","command":"..."}`
(the host spawns it detached through a login shell and replies
`executed`/`error`; a later `executed:false` follows if the shell reports
126/127 within a few seconds), and `{"op":"record","provider":"apps","result":"apps:x","title":"X"}`
(frecency history; see below).

## Result metadata

- `title`, `subtitle`, `icon` — display fields.
- `keywords` — optional space-separated aliases matched by the frontend fuzzy pass.
- `icons` — optional ordered candidate list of icon names/absolute paths. The frontend resolves the first entry that exists in the active theme; use it so results survive arbitrary icon themes.
- `fallbackIcon`, `fallbackColor` — optional glyph/color used only when every icon candidate misses.
- `score` — advisory 0..1; blended with the frontend fuzzy score.
- `provider` — set by the host during merge.
- `id` — stable per result and unique per query meaning (for example `run:<query>`);
  selection follows it while rows stream in, and a confirmation sheet is bound
  to it plus the exact query.
- `fallback: true` — always ranked after every non-fallback row (the `Run:` row
  and PATH command rows). The `run` provider is always treated as fallback.
- `recent` — set by the host, 0..1, from frecency history
  (`$XDG_STATE_HOME/pallet/history.json`; `PALLET_HISTORY=0` disables it;
  `run` rows are never recorded). It only reorders rows within the same match
  tier (exact > prefix > word > substring > subsequence).
- Rows from the `files` provider rank below every other row that matches at
  substring tier or better unless the query has file intent (`/`, `~` or
  `.`), so an exact-named Omarchy, system or app row beats an equally named
  file or folder.

## Action types

- `launch` — argv array, spawned detached by the host as `bash -lc 'exec "$@"' bash <argv>`
  (Omarchy's `Util.execArgv`; no interpolation); a missing command is reported back
- `shell` — `command` string run as `bash -lc <command>`, detached. Only for trusted
  command strings that come from Omarchy's own menu files (never from a query)
- `copy` — put text on the clipboard (frontend)
- `open` — path or url via xdg-open (frontend)
- `custom` — provider-defined payload sent back to the owning provider

## Action metadata

```json
{
  "type": "shell",
  "title": "Update Omarchy",
  "command": "omarchy-launch-floating-terminal-with-presentation omarchy-update",
  "danger": "confirm",
  "tone": "positive",
  "confirmation": {"title": "Update Omarchy?", "detail": "Runs Omarchy's own menu command: omarchy-launch-floating-terminal-with-presentation omarchy-update"}
}
```

- `title` — preferred panel label.
- `danger: "confirm"` — requires a second Enter on the confirmation sheet; behavioral, independent of visual tone.
- `tone` — optional visual meaning for confirmation-gated actions: `positive` (green), `warning` (amber), or `danger` (red).
- `confirmation.title` / `confirmation.detail` — text shown in the sheet.

## Rules

1. argv is passed to `exec "$@"`, never interpolated into a shell string. `shell`
   commands are only ever trusted Omarchy menu actions.
2. Cancellation is cooperative: on cancel, stop work and emit a cancelled reply for the target id.
3. Provider scores are advisory; the frontend applies its fuzzy pass.
4. Respond within 150 ms or stream partial results; the host cancels stale queries.
5. A manifest declares every executable the provider may run; undeclared executions are bugs.
