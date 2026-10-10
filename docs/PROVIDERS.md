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

## Messages

Host to provider:

```json
{"id": "q1", "op": "search", "query": "fire"}
{"id": "q2", "op": "cancel", "target": "q1"}
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
    "actions": [
      {"type": "launch", "argv": ["firefox"]},
      {"type": "copy", "text": "firefox"}
    ]
  }
]}
```

## Action types

- `launch` — argv array, executed directly, no shell
- `copy` — put text on the clipboard
- `open` — url via xdg-open
- `custom` — provider-scoped identifier, handled by the provider in a follow-up request

## Rules

1. argv is executed without a shell. No string interpolation into shell commands, ever.
2. Cancellation is cooperative: on cancel, stop work and emit a cancelled reply for the target id.
3. Provider scores are advisory; the host applies its own ranking (history, recency, fuzzy match).
4. Respond within 150 ms or stream partial results; the host cancels stale queries when input changes.
5. A manifest declares every executable the provider may run; undeclared executions are bugs.
