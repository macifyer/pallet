# Pallet

A keyboard-driven command palette for Omarchy on Arch/Hyprland, built on Quickshell. Summon it, type, act — applications, windows, files, system commands, Omarchy actions, installed plugins, run-any-command, and Obsidian actions in one overlay.

## Install (Omarchy Quattro)

```sh
omarchy plugin add https://github.com/macifyer/pallet.git --enable
```

ALT+SPACE toggles the palette; SUPER+SPACE stays on the stock Omarchy menu.

## Update

```sh
omarchy plugin update io.github.macifyer.pallet
```

Development:

```sh
git clone git@github.com:macifyer/pallet.git \
    ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy-shell shell rescanPlugins && omarchy plugin enable io.github.macifyer.pallet
```

## Search scopes

Use prefixes when you want one provider focused instead of mixed search:

- `files:invoice` or `f:invoice` — files only
- `obsidian:todo` or `o:todo` — Obsidian actions only
- `apps:zen` or `a:zen` — applications only

Mixed search remains the default; scopes are additive, not required.

## Obsidian setup

The Obsidian provider uses official `obsidian://` actions (open, daily, new, search, choose-vault). Vault contents are not indexed here yet, and Pallet never pipes note text into a shell.

### URI requirements

Obsidian normally registers `obsidian://` after the app is installed. On Linux, your desktop entry should pass URIs with `%u`, for example:

```desktop
Exec=obsidian %u
```

AppImage installs may need you to extract the AppImage and point the desktop entry at the unpacked executable. Verify with:

```sh
xdg-open 'obsidian://choose-vault'
```

### CLI setup

Optional Obsidian CLI actions require Obsidian installer version 1.12.7+.

1. In Obsidian, open Settings → General → Command line interface.
2. Enable it and let Obsidian register the CLI.
3. On Linux, confirm `~/.local/bin/obsidian` exists and `~/.local/bin` is in PATH.
4. Restart your terminal, then run:

```sh
obsidian help
```

Pallet includes an `Obsidian CLI reference` action when `obsidian` is available. Future AI/CLI actions will use only capability-checked commands, not guessed IDs.

## Files, yazi, and fzf direction

The files provider is name-based and fast. A later file scope can wrap visible terminal pickers such as `yazi` or `fzf`, but Pallet will not replace them with opaque shell command execution from the search text.

## Security posture

- Search text is URI-encoded for app targets and is never executed directly by Pallet.
- The explicit `Run:` command result opens a visible terminal and carries confirmation.
- Destructive session/package actions keep confirmation sheets.
- CLI and AI integrations must be opt-in, documented, and capability checked.

## Credits

- MaNi4/omarchy-search-menu-items (MIT), bjarneo/omarchy-shell-plugins (MIT)
- Raycast, Vicinae, Wox, Ueli — inspiration only
