# omarchy provider

Parity with the native Omarchy menu: every entry of Omarchy's own menu
definition, searchable from the palette and run *by Omarchy itself*.

## Source of truth

| What | Source file (Omarchy) |
|---|---|
| Menu tree: ids, labels, aliases, `when`, `disabled`, `action` | `default/omarchy/omarchy-menu.jsonc` under `$OMARCHY_PATH`, `/usr/share/omarchy` or `~/.local/share/omarchy` |
| User overlay, merged per key like `MenuModel.mergeMenuSources` | `~/.config/omarchy/extensions/omarchy-menu.jsonc` |
| Running an entry | `bin/omarchy-menu` (`summon <id>`: leaf → runs its action, submenu → opens it) |
| Guard semantics (8 batched groups, package snapshot, `omarchy-pkg-present/missing`, `omarchy-cmd-present/missing`) | `shell/menu/MenuModel.js` (`guardScript`) |

Pallet never re-implements a menu command. Each row's action is
`["omarchy-menu", "summon", "<id>"]` (argv, no shell), so the menu's own
action, any terminal wrapper and any follow-up prompt are exactly what the
native menu does. "Copy command" copies the menu's `action` string for
inspection only; it is never executed by Pallet.

The file is re-read only when its mtime/size changes (about 13 ms for the
411-entry menu); a search is about 1 ms.

## Guards (`when` / `disabled`)

Omarchy's own trusted conditions are evaluated the way the native menu does:
one `bash -c` (own session, 8 s timeout, process group killed on timeout) runs
the conditions in 8 background groups with a pacman package snapshot. Answers
are cached for 30 s and refreshed in a background thread on `warm` and on
search, so typing never waits on them. This is a deliberate decision: it runs
only conditions shipped in Omarchy's menu file (or the user's own overlay),
never anything derived from a query, and it is not PATH discovery.

- `when` false (on the entry or any ancestor): the row is hidden. Toggle pairs
  (Nightlight On/Off, …) therefore show only the side that applies.
- `disabled` true: the row stays listed as `· ✓ installed` with no run action.
- Unknown (not evaluated yet, timed out, or a condition that exits its group):
  the row summons its **parent** menu instead (`· opens in the Omarchy menu`),
  so the native menu applies its guard. A guarded action is never run blind.
- `checked` is not evaluated (Pallet has no checkmarks).

Entries that cannot be reached in the native menu (orphans, or children of an
entry that has its own action) are skipped.

## Confirmations

Rows matching these id prefixes carry `danger: "confirm"` (tone in brackets):

- `system.suspend`, `system.hibernate`, `system.logout`, `system.reboot` (warning), `system.shutdown` (danger)
- `remove.*` (danger), `setup.reset` (danger), `setup.plugin.remove` (danger)
- `setup.direct-boot`, `setup.security.*`, `setup.network.dns.*` (warning)
- `update.omarchy`, `update.themes` (positive); `update.channel.*`, `update.config.*`,
  `update.process.*`, `update.hardware.*`, `update.firmware`, `update.password.*`, `update.time` (warning)
- `trigger.reminder.clear` (danger), `trigger.hardware.hybrid-gpu-*` (warning)
- `appearance.branding.about.default`, `appearance.branding.screensaver.default` (warning)
- `install.*` (positive), except the pickers `install.package`, `install.aur`,
  `install.webapp`, `install.tui` and `update.timezone`, which only open a chooser.

Lock is deliberately unconfirmed. Submenus never confirm (they only open).

## Curated extras

Shell panels and two actions not reachable as single menu rows. An extra is
dropped when the menu already has an entry running the identical command.

| Entry | argv | Source |
|---|---|---|
| Network | `omarchy-shell shell summon omarchy.network` | `default/hypr/bindings/utilities.lua` (`SUPER+CTRL+N`), `shell/plugins/panels/network` |
| Bluetooth | `… summon omarchy.bluetooth` | `utilities.lua` (`SUPER+CTRL+B`), `shell/plugins/panels/bluetooth` |
| Audio | `… summon omarchy.audio` | `utilities.lua` (`SUPER+CTRL+A`), `shell/plugins/panels/audio` |
| Power | `… summon omarchy.power` | `utilities.lua` (`SUPER+CTRL+P`), `shell/plugins/panels/power` |
| Display (brightness) | `… summon omarchy.monitor` | `utilities.lua` (`SUPER+CTRL+D`), `shell/plugins/panels/monitor` |
| Calendar | `… summon omarchy.clock` | `utilities.lua` (`SUPER+CTRL+ALT+D`) |
| World Clock | `… summon omarchy.elsewhen` | `utilities.lua` (`SUPER+CTRL+ALT+E`), `shell/plugins/panels/elsewhen` |
| Tailscale | `… summon omarchy.tailscale` | `shell/plugins/panels/tailscale` (does nothing if the panel is not loaded) |
| Weather | `… summon omarchy.weather` | `shell/plugins/panels/weather` |
| Toggle Animations | `omarchy-toggle-animations` | `bin/omarchy-toggle-animations` |
| Omarchy Menu | `omarchy-menu toggle` | `bin/omarchy-menu` |

`bin/omarchy-shell` accepts the three-argument `shell summon <panel>` form.
Keybindings use `toggle`; Pallet uses `summon` so choosing a row never closes
an already open panel.

## Tests

`tests/test_omarchy.py` uses a trimmed fixture
(`tests/fixtures/omarchy/default/omarchy/omarchy-menu.jsonc`) and, when
`/workspace/omarchy-src` is present, also parses the real menu.
`tests/test_system.py` checks every extra's command exists in Omarchy's `bin/`.
