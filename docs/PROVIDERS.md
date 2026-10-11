# Provider protocol

A provider is a subprocess speaking newline-delimited JSON over stdio. It is never a QML plugin, never executes arbitrary shell commands from search text, and everything it runs is declared in its manifest and visible to the user.

## Manifest

```json
{"name": "apps", "exec": ["python3", "providers/apps/provider.py"], "capabilities": ["search"]}
```

## Messages

Host to provider: `{"id":"q1","op":"search","query":"fire"}` · `{"id":"q2","op":"cancel","target":"q1"}` · `{"id":"a1","op":"execute","action":{...}}`.

Provider to host: `{"id":"q1","results":[...]}` · `{"id":"a1","executed":true}`.
The host tags merged results with their provider name; custom actions route only back to that owning provider.

## Result metadata

- `title`, `subtitle`, `icon` — display fields.
- `keywords` — optional space-separated aliases matched by the frontend fuzzy pass.
- `icons` — optional ordered candidate list of icon names/absolute paths. The frontend resolves the first entry that exists in the active theme; use it so results survive arbitrary icon themes.
- `fallbackIcon`, `fallbackColor` — optional glyph/color used only when every icon candidate misses.
- `score` — advisory 0..1; blended with the frontend fuzzy score.
- `provider` — set by the host during merge.

## Action types

- `launch` — argv array, executed directly by the frontend, no shell
- `copy` — put text on the clipboard (frontend)
- `open` — path or url via xdg-open (frontend)
- `custom` — provider-defined payload sent back to the owning provider

## Action metadata

```json
{
  "type": "launch",
  "title": "Update Omarchy",
  "argv": ["foot", "--", "omarchy", "update"],
  "danger": "confirm",
  "tone": "positive",
  "confirmation": {"title": "Update Omarchy?", "detail": "Runs the official Omarchy update in a terminal."}
}
```

- `title` — preferred panel label.
- `danger: "confirm"` — requires a second Enter on the confirmation sheet; behavioral, independent of visual tone.
- `tone` — optional visual meaning for confirmation-gated actions: `positive` (green), `warning` (amber), or `danger` (red).
- `confirmation.title` / `confirmation.detail` — text shown in the sheet.

## Rules

1. argv is executed without a shell. No string interpolation into shell commands.
2. Cancellation is cooperative: on cancel, stop work and emit a cancelled reply for the target id.
3. Provider scores are advisory; the frontend applies its fuzzy pass.
4. Respond within 150 ms or stream partial results; the host cancels stale queries.
5. A manifest declares every executable the provider may run; undeclared executions are bugs.
