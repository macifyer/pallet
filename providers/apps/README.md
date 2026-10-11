# apps provider

Searches installed applications from XDG `.desktop` entries and launches them
by raw argv — never through a shell.

## Index sources

- `~/.local/share/applications`
- `~/.local/share/flatpak/exports/share/applications`
- `/usr/local/share/applications`
- `/usr/share/applications`
- `/var/lib/flatpak/exports/share/applications`

Files are deduped by filename with user directories winning, matching XDG
precedence. Entries are skipped when `NoDisplay`/`Hidden`, `Terminal=true`,
or when the binary cannot be resolved (`TryExec` when declared, otherwise
`Exec` argv[0]) — this hides the debris uninstalls leave behind.

## Desktop actions

The freedesktop spec lets entries declare extra invocations via `Actions=`
plus `[Desktop Action ...]` groups — Firefox: New Window / New Private
Window, terminals: new tab/window, and so on. Launchers are expected to
expose these, so each one becomes a titled `launch` action in the panel
with zero per-app code. Capped at six per app to keep the action panel
usable.

Enter always runs the entry's primary `Exec`; declared actions live in the
Tab panel under their own names.

## Freshness

The index is built once at provider start. Newly installed or removed apps
(and their actions) appear after the provider restarts (shell restart).
Live re-indexing via file watching is deferred.
