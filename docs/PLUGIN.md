# Pallet as an Omarchy plugin

Pallet is an Omarchy Quattro shell plugin with two kinds: `overlay` (the
palette window) and `service` (hotkey registration). The contract is a root
`manifest.json` plus a QML entry point per kind; validation is the same check
the shell runs at load: `omarchy plugin validate <path>`.

## Lifecycle contract

| Shell call | Routed to |
|---|---|
| `omarchy-shell shell summon io.github.macifyer.pallet '{}'` | `PalletOverlay.qml -> open()` |
| `omarchy-shell shell hide io.github.macifyer.pallet` | `PalletOverlay.qml -> close()` |
| `omarchy-shell shell toggle io.github.macifyer.pallet` | `PalletOverlay.qml -> toggle()` |

`keepLoaded: true` keeps both components alive so the Python host process
spawned by `ProviderBridge` stays warm between summons. As a plugin, Pallet
runs inside the long-lived omarchy-shell process — never start a second
Quickshell instance for it. (`qs -p shell` remains for standalone, non-Omarchy
development.)

## The hotkey (service kind)

`Service.qml` registers `ALT+SPACE -> omarchy-shell shell toggle
io.github.macifyer.pallet` at runtime, after the pattern of MaNi4's plugin:

- Registration goes through `hyprctl eval` with `hl.bind(...)` Lua —
  `hyprctl keyword bindd` does not land reliably at runtime (learned the hard
  way: a bind that logged success while Hyprland held nothing).
- Registration is verified: 500 ms after registering, the binds are re-read;
  the log says `confirmed` or warns that the bind did not land.
- Existing binds are read first (`hyprctl binds -j`). If ALT+SPACE is taken,
  Pallet logs a warning and does not override it; bind the toggle yourself.
- Our binding is identified by its description (`Pallet command palette`), so
  re-registration never duplicates it.
- Hyprland drops runtime bindings on `hyprctl reload`. A socket2 watcher
  (`configreloaded`) re-asserts the bind. This needs `socat`; without it the
  bind vanishes on reload until the plugin reloads.
- Disabling/removing the plugin destroys the service, which unbinds the combo
  it registered (`hl.unbind`).

## Develop against the real shell

The validator rejects symlinked plugin folders outright, so the development
checkout IS the plugin directory — a real git clone inside the plugins dir:

```sh
git clone git@github.com:macifyer/pallet.git \
    ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy-shell shell rescanPlugins
omarchy plugin validate ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy plugin enable io.github.macifyer.pallet
```

Edit, commit, and push from that directory. The shell auto-reloads on save,
and `git pull` there is the update loop. A separate clone elsewhere (e.g.
~/Projects/pallet) is only useful for standalone `qs -p shell` testing.

## Troubleshooting

- **Never run `omarchy plugin remove` with your terminal cd'd inside the
  plugin dir.** The removal deletes your cwd; every later command in that
  shell dies with `getcwd: cannot access parent directories`. `cd ~` first.
- **Plugin changes that "should" work but don't** — restart the shell:
  `omarchy-restart-shell`. The long-lived process accumulates poisoned state
  across many plugin reload cycles (this cost us an afternoon: a phantom
  "File name case mismatch" that survived pristine files).
- **"File name case mismatch" on a correctly-cased file** — clear the
  runtime cache and restart: `rm -rf ~/.cache/quickshell`,
  `omarchy-restart-shell`.
- **Entry point naming** — service entry points are named `Service.qml` by
  convention (first-party plugins and MaNi4's working plugin alike).
- **Fresh reinstall:** `omarchy plugin remove io.github.macifyer.pallet`,
  then `omarchy plugin add <url> --enable` (from a sane cwd).

## Updating (git installs)

```sh
omarchy plugin update io.github.macifyer.pallet
```

## Inspect

```sh
omarchy plugin list --json | jq '.[] | select(.id == "io.github.macifyer.pallet")'
qs log -p "$OMARCHY_PATH/shell" --tail 100
hyprctl binds -j | jq '.[] | select(.description == "Pallet command palette")'
```

The last command is ground truth for the hotkey: it shows the binding
Hyprland actually holds, not what any log line claims.

## Publish checklist

- Flip the repo public (required for `omarchy plugin add <url>` to work for
  anyone but you):

  ```sh
  gh repo edit macifyer/pallet --visibility public --accept-visibility-change-consequences
  gh repo edit macifyer/pallet --add-topic omarchy --add-topic omarchy-plugin \
      --add-topic quickshell --add-topic hyprland --add-topic launcher
  ```

- README, LICENSE, optional `preview.png` at repo root
- `omarchy plugin validate .` clean
- Submit the listing; installs are `omarchy plugin add <git-url> --enable`
