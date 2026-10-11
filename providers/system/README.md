# system provider

System power, session, and update actions — the native Omarchy menu's
commands, surfaced as palette results.

## Entries

| Entry | Command | Confirmation |
|---|---|---|
| Lock | `omarchy system lock` | no |
| Omarchy Menu | `omarchy menu toggle` | no |
| Suspend | `systemctl suspend` | yes |
| Update Omarchy | `foot -- omarchy update` | yes |
| Log Out | `omarchy system logout` | yes |
| Reboot | `omarchy system reboot` | yes |
| Shut Down | `omarchy system shutdown` | yes |

The `omarchy system *` commands close application windows before acting,
matching the native menu's logout/reboot/shutdown behavior.

## Safety model

- Update runs Omarchy's official orchestrated update (`omarchy update`) in a
  visible foot terminal — snapshot, packages, migrations, shell restart.
  Never a raw pacman/AUR command.
- Lock is deliberately ungated: locking must stay one keystroke away.
- Everything disruptive (suspend, logout, reboot, shutdown, update) carries
  `danger: "confirm"` and requires a second Enter on the confirmation sheet.
- Every entry also offers "Copy command" so users can inspect what runs.

## Deferred

- Hibernate (needs an `omarchy-hibernation-available` runtime check).
- Config editing entries (Hyprland, shell.json) — needs an editor choice.
- Theme/wallpaper pickers.
