# Pallet development roadmap

This is the implementation sequence, not a claim that all features exist.
Version numbers are assigned to coherent releases per VERSIONING.md, not to
individual checklist items. Never describe a prepared patch as pushed.

## 1. Launcher foundations (in progress)

Implemented in 0.9.0, native-session verification still required:
- [x] Terminal=true desktop entries and terminal-wrapped desktop actions.
- [x] XDG-aware roots, desktop-ID precedence, and stable application IDs.
- [x] Refresh on later searches, including in-place edits and removed entries.
- [x] Isolated regression tests; no installed programs launched during discovery.

Next foundation patches:
- [ ] Reject stale responses by query ID in the frontend, including edits,
      clearing, dismissing, reopening, and changing scope.
- [ ] Preserve confirmations only for the exact selected result/query.
- [ ] Show provider failures/timeouts and propagate action failures.
- [ ] Ensure command suggestions cannot outrank meaningful local matches.
- [ ] Conservative exact/prefix PATH command discovery and user-saved TUI
      profiles; never execute candidate binaries to discover capabilities.

### Terminal application usage

Search the application's desktop name or executable name. Enter launches its
primary action; Tab exposes the app's declared alternate actions. Terminal
apps are labeled Terminal application. Discovery is independent of whether
the installer was pacman, AUR, Flatpak, Snap, AppImage tooling, or git: a
visible desktop entry with a resolvable Exec/TryExec is required.

Pallet prefers `xdg-terminal-exec -- <argv>`, letting that dispatcher select
the configured terminal. Without it, fallbacks are foot, kitty, alacritty,
and xterm in that order. Without any supported launcher the result remains
visible with an explanation and no actions. No shell string is constructed.

Catalog refresh occurs on the next nonempty app search after 10 seconds,
not via a background watcher. Changes to the shell process's PATH or XDG
environment may require a shell restart. User roots precede system roots;
Flatpak and Snap exports are also considered. Application IDs now use
`apps:<desktop-file-id>`, so duplicate display names no longer collide.

This is not complete desktop-spec parity: D-Bus-only activation, localized
names, desktop Path working directories, and arbitrary embedded Exec field
codes are not newly implemented here. Tools without a desktop entry still
use the explicit command runner until PATH discovery/profiles land.

Test on Omarchy after pulling:

```sh
python3 scripts/check_release.py
python3 -m unittest discover -s tests -v
omarchy plugin validate .
omarchy restart shell
```

Search a known installed terminal app that actually has a desktop entry,
launch it directly and through Tab, and verify normal GUI apps still open.
The new tests use synthetic entries and mocked executable lookup; they do
not launch terminals, install packages, or read personal vaults.

## 2. Reusable scoped views and setup

- [ ] Internal navigation actions, scope header, Back/Esc semantics, query and
      selection restoration, and forms shared between integrations.
- [ ] Obsidian setup screen: instructions, explicit vault selection, persistent
      settings, URI handoff test, and distinct CLI-readiness checks.
- [ ] Theme tokens, readable contrast, and reduced-motion behavior before
      optional translucent/liquid-glass styling.

## 3. In-Pallet Obsidian search

- [ ] Opt-in local filename index for .md, .canvas, and .base.
- [ ] Vault labels, correct target-vault opening, bounded refresh, no silent
      content scanning or AI transmission.
- [ ] Explicit creation with destination and collision protection; supported
      canvas/base/folder operations only after capability verification.
- [ ] Content/tag/property filters after filename search is dependable.

## 4. Recents and favorites

- [ ] Empty-query recents, pinning, bounded ranking boosts, and stale-result
      cleanup. History can be cleared or disabled; commands/secrets are not
      recorded by default.

## 5. Daily-use tools and richer files

- [ ] Opt-in clipboard history with retention/deletion controls.
- [ ] Manual snippet insertion first; expansion/automation later.
- [ ] File filters, metadata, previews, reveal-selected-file behavior, and
      optional Open in Yazi / visible fzf picker integration.
- [ ] Calculator and timers from the original persistent-tools plan.

## 6. Explicit AI destination and release readiness

- [ ] Opt-in AI connection/capability setup; no requests while merely typing.
- [ ] Action review, permissions, and separate consent for vault/file access.
- [ ] Provider SDK/diagnostics, clean-install/native UI checks, accurate README,
      license notices, release tags, and registry submission.

Keep Omarchy/Hyprland specifics behind adapters where practical. No new
system daemon, AI agent, clipboard collector, or third-party plugin should
be installed or enabled silently to satisfy these milestones.
