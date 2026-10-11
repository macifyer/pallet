# Provider protocol

A provider is a subprocess speaking newline-delimited JSON over stdio. It is never a QML plugin, never executes arbitrary shell commands from search text, and everything it runs is declared in its manifest and visible to the user.

## Manifest

```json
{
  "name": "apps",
  "description": "Search installed applications",
  "exec": ["python3", "providers/apps/provider.py"],
  "triggers": [],
  "capabilities": ["search"]
}
```

`capabilities` advertises `search` and, for providers that can act on their own results after the fact, `execute`.

## Messages

Host to provider:

```json
{"id": "q1", "op": "search", "query": "fire"}
{"id": "q2", "op": "cancel", "target": "q1"}
{"id": "a1", "op": "execute", "action": {"type": "custom", "id": 12}}
```

Provider to host:

```json
{"id": "q1", "results": [
  {
    "id": "firefox.desktop",
    "title": "Firefox",
    "subtitle": "Web browser",
    "icon": "firefox",
    "score": 0.9,
    "keywords": "browser web internet",
    "actions": [
      {"type": "launch", "title": "Launch", "argv": ["firefox"]},
      {"type": "copy", "title": "Copy name", "text": "firefox"}
    ]
  }
]}
{"id": "a1", "executed": true}
```

The `execute` op goes only to the provider that authored the result: the host tags each result with its provider name during merge (overriding nothing already set), and the frontend includes that name when it asks for a `custom` action to run.

## Result metadata

- `title`, `subtitle`, `icon` — display fields.
- `keywords` — optional space-separated alias string. The frontend's fuzzy pass matches it with the same subsequence scoring as title and subtitle, so aliases like `sleep` → "Suspend" or `halt` → "Shut Down" survive ranking instead of being dropped. Emit it whenever the provider's own alias matching can find a result that its title would not.
- `score` — advisory 0..1; blended with the frontend fuzzy score.
- `provider` — set by the host during merge.

## Action types

- `launch` — argv array, executed directly by the frontend, no shell
- `copy` — put text on the clipboard (frontend)
- `open` — url via xdg-open (frontend)
- `custom` — provider-defined payload; the frontend sends it back to the owning provider with op `execute` (menu presses, window control, anything needing provider-side handles)

## Action metadata

Every action may carry display metadata. Providers own their action labels; the frontend invents one only when a provider did not.

```json
{
  "type": "custom",
  "kind": "system-update",
  "title": "Update Omarchy",
  "danger": "confirm",
  "confirmation": {
    "title": "Update Omarchy?",
    "detail": "Runs 'omarchy update' in a terminal: packages, migrations, and a snapshot."
  }
}
```

- `title` — preferred label in the action panel; when absent, the frontend derives one from type and kind.
- `subtitle` and `icon` are reserved for the panel's detailed rows; providers may emit them today without effect.
- `danger: "confirm"` — implemented. Enter on such an action does not execute: the panel swaps to a red-bordered confirmation sheet showing `confirmation.title`/`confirmation.detail`, and only a second Enter runs the action. Esc (or changing the selection) cancels back to the action list. Use it for anything where a mistaken keypress is expensive — updates, removals, power actions.

## Rules

1. argv is executed without a shell. No string interpolation into shell commands, ever.
2. Cancellation is cooperative: on cancel, stop work and emit a cancelled reply for the target id.
3. Provider scores are advisory; the host applies its own merge, the frontend its own fuzzy pass.
4. Respond within 150 ms or stream partial results; the host cancels stale queries when input changes.
5. A manifest declares every executable the provider may run; undeclared executions are bugs.
