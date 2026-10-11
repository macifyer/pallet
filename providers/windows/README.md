# windows provider

Search and control currently mapped Hyprland windows using `hyprctl clients -j`.

## Search fields

- Window title
- Current window class / initial class
- Workspace name or ID

The focused window receives a small advisory-score boost. The frontend's fuzzy
ranking remains the final ordering pass.

## Actions

| Action | Hyprland dispatcher |
|---|---|
| Focus window | `focuswindow address:0x...` |
| Close window | `closewindow address:0x...` |
| Toggle floating | `togglefloating address:0x...` |
| Toggle fullscreen | focus exact address, then `fullscreen 0` |
| Copy title | Frontend clipboard action |

Window addresses are ephemeral. Before every custom action the provider refreshes
`hyprctl clients -j` and refuses addresses not currently present. No shell string
is created from search text or window titles.

Deferred: move-to-workspace (needs a workspace picker), pin.
