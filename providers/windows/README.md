# windows provider

Search and control currently mapped Hyprland windows using `hyprctl clients -j`.

## Search fields

- Window title
- Current window class / initial class
- Workspace name or ID

The focused window receives a small advisory-score boost. The frontend's fuzzy
ranking remains the final ordering pass.

## Actions — Lua-era dispatching

Hyprland 0.55 removed legacy string dispatchers: `hyprctl dispatch` wraps its
argument as `hl.dispatch(<arg>)`, so every call is a `hl.dsp.*`
dispatcher-object expression. The compositor replies `ok` or an error
message; the provider checks both the exit code and the reply text.

| Action | Dispatcher object |
|---|---|
| Focus window | `hl.dsp.focus({ window = "address:0x..." })` |
| Close window | `hl.dsp.window.close({ window = "address:0x..." })` |
| Toggle floating | `hl.dsp.window.float({ action = "toggle", window = "address:0x..." })` |
| Toggle fullscreen | `hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle", window = "address:0x..." })` |
| Copy title | Frontend clipboard action |

Every operation targets the exact window directly — no focus stealing.
Window addresses are ephemeral: before every custom action the provider
refreshes `hyprctl clients -j` and refuses addresses not currently present.
Lua snippets are built from regex-validated hex addresses and fixed kind
constants; search text and window titles never reach them.

Deferred: move-to-workspace (needs a workspace picker), pin.
