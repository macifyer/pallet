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

## Versions and development checks

The root `manifest.json` is the single source of the product version:
`MAJOR.MINOR.PATCH` in JSON and `vMAJOR.MINOR.PATCH` for release tags.
Bundled providers inherit the product version. Manifest `schemaVersion` is
separate and must not track product releases. See [Versioning and releases](docs/VERSIONING.md)
and [Changelog](CHANGELOG.md). Old version numbers in git history remain historical.

Read the installed checkout version without relying on a stale README label:

```sh
python3 -c 'import json; print(json.load(open("manifest.json"))["version"])'
python3 scripts/check_release.py
python3 -m unittest discover -s tests -v
```

Host smoke test (does not execute result actions):

```sh
printf '%s\n' '{"id":"t","op":"search","query":"obsidian:notes"}' | python3 src/host.py
```

Expect a JSON reply on stdout with `id: t`, `scope: obsidian`, `bare: notes`,
and a `results` array. The `host: providers up` line is stderr diagnostics,
not a successful search response. On EOF the host lets the final query
finish within the merge deadline before shutting providers down. Empty
results can still indicate an unavailable, failing, or slow provider.
Python fixture tests do not replace native QML/Hyprland/Obsidian validation.

## Search scopes

Use prefixes when you want one provider focused instead of mixed search:

- `files:invoice` or `f:invoice` — files only
- `obsidian:todo` or `o:todo` — Obsidian actions only
- `apps:zen` or `a:zen` — applications only

Mixed search remains the default; scopes are additive, not required.

## Obsidian setup

The Obsidian provider uses official `obsidian://` actions (open, daily, new, search, choose-vault). Vault contents are not indexed here yet, and Pallet never pipes note text into a shell.

### Search versus creation

- `obsidian:project` or `o:project` offers **Search Obsidian: project**.
  Selecting it opens Obsidian's search; Pallet does not yet list local vault notes.
- `obsidian project` provides the same explicit Obsidian handoff from mixed search.
- `obsidian:new note My Note` or `obsidian create note My Note` offers an
  explicitly named creation action with a confirmation sheet. Generic
  searches never imply creation, even when no notes match.
- `obsidian:new note` is a non-executable instruction row until a name is supplied.
- New-note names must be one printable filename of at most 200 characters;
  slashes, backslashes, dot/dot-dot, and control characters are rejected.
- `obsidian:search new note Project` forces a search for the literal phrase
  `new note Project` instead of treating it as a creation command.
- `obsidian:daily` opens or creates today's note through Obsidian's Daily notes
  plugin; `obsidian:vault` opens the vault manager.
- `obsidian:setup` and `obsidian:cli` open the official setup documentation.
  These are guide links, not a Pallet onboarding screen or readiness test.

URI parameters are percent-encoded. Creation sends only `name`: no `path`,
`file`, `overwrite`, `append`, `content`, or `clipboard` parameter. Obsidian
chooses the destination and new-note location; Pallet does not yet configure
or verify a target vault. Review the confirmation and the active vault before
creating. Setup UI, saved vault selection, note indexing, canvas/base/folder
creation, and AI command execution remain future work.

The host now includes an optional `scope` field in search messages so the
Obsidian provider distinguishes explicit scoped searches from unrelated
mixed searches. Existing providers can ignore this additive metadata.

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

Pallet offers an `Obsidian CLI Setup Guide` link. An `obsidian` executable
on PATH proves neither CLI registration nor readiness, so Pallet no longer
labels executable presence as a capability check or launches a help shell
from this result. Future AI/CLI actions require real capability checks.

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
