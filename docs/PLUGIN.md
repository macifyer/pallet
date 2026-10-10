# Pallet as an Omarchy plugin

Pallet is an Omarchy Quattro shell plugin of kind `overlay`. The contract is a
root `manifest.json` plus a QML entry point per kind; validation is the same
check the shell runs at load: `omarchy plugin validate <path>`.

## Lifecycle contract

| Shell call | Routed to |
|---|---|
| `omarchy-shell shell summon io.github.macifyer.pallet '{}'` | `PalletOverlay.qml -> open()` |
| `omarchy-shell shell hide io.github.macifyer.pallet` | `PalletOverlay.qml -> close()` |

`keepLoaded: true` keeps the component alive so the Python host process
spawned by `ProviderBridge` stays warm between summons. As a plugin, Pallet
runs inside the long-lived omarchy-shell process — never start a second
Quickshell instance for it. (`qs -p shell` remains for standalone, non-Omarchy
development.)

## Develop against the real shell

```sh
ln -s ~/Projects/pallet ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy-shell shell rescanPlugins
omarchy plugin validate ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy plugin enable io.github.macifyer.pallet
```

The plugin directory may itself be a symlink (removal unlinks it); no symlinks
are allowed inside the folder. Saving files under the plugins directory
auto-reloads the plugin.

## Bind it

`hyprland.conf`:

```
bind = SUPER, K, exec, omarchy-shell shell summon io.github.macifyer.pallet '{}'
```

Esc or a backdrop click closes it. A MaNi4-style self-registering runtime
binding (a `service` kind using `hyprctl eval`) is a planned upgrade, which is
why the manifest does not declare `service` yet.

## Inspect

```sh
omarchy plugin list --json | jq '.[] | select(.id == "io.github.macifyer.pallet")'
qs log -p "$OMARCHY_PATH/shell" --tail 100
```

## Publish checklist

- Public git repo; manifest keeps `id: io.github.macifyer.pallet`
- README, LICENSE, optional `preview.png` at repo root
- `omarchy plugin validate .` clean
- Submit the listing; installs are `omarchy plugin add <git-url> --enable`
