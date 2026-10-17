# Changelog

Release numbers come from the root manifest.json. This changelog starts with
0.8.1; it is not a reconstructed or retagged history of earlier commits.

## [Unreleased]

## [0.9.0]

### Added
- Discover and launch Terminal=true desktop applications and their declared
  desktop actions, using xdg-terminal-exec or supported terminal fallbacks.
- Resolve application directories from XDG_DATA_HOME and XDG_DATA_DIRS,
  with Flatpak/Snap export fallbacks and recursive desktop-file discovery.
- Identify application results by desktop-file ID instead of display name.
- Report missing terminal launchers as non-executable result rows.
- Add 12 isolated application-discovery tests and a staged development roadmap.

### Fixed
- Respect Hidden, NoDisplay, OnlyShowIn, NotShowIn, and TryExec filtering;
  higher-priority hidden desktop entries suppress lower-priority copies.
- Refresh the application catalog on a search after the 10-second interval,
  including in-place edits, new binaries, and removed desktop entries.
- Preserve quoted arguments, handle supported standalone Exec field codes,
  and reject malformed or unknown codes instead of guessing shell commands.

### Scope
- Desktop entries only: arbitrary PATH discovery, saved TUI profiles,
  stale-query UI handling, and provider diagnostics are separate follow-ups.
- Existing result IDs change from display-name-based to desktop-ID-based.
- Automated fixtures do not prove terminal launching on a real Omarchy session.

## [0.8.2]

### Fixed
- Obsidian searches never generate a new-note action merely from query length.
- Require explicit `new note NAME` or `create note NAME` intent; validate the
  name and confirm creation without sending overwrite/append parameters.
- Pass optional scope metadata to providers so generic launcher queries do
  not accidentally become Obsidian searches.
- Replace the executable-presence-based CLI help shortcut with an honest
  official CLI setup-guide link, not a claim of CLI readiness.
- Preserve query text through URI encoding and add 12 intent/protocol/host
  tests that do not launch Obsidian or touch a user's vault.

This is a search-intent correction, not local vault indexing or a setup UI.

## [0.8.1]

### Fixed
- Wait for the final pending search on stdin EOF before terminating providers.
  A piped request now gets a response within the existing merge deadline.
- Await provider shutdown and kill children that ignore termination.

### Development
- Define the root manifest as the single source of the product version.
- Document full three-part versions, v-prefixed release tags, and separate
  schema/protocol compatibility from product release numbers.
- Add isolated host regression tests, release-validation tests, and CI for
  Python syntax and release metadata. No Hyprland or personal vault required.

Earlier development milestones are recorded in git history. Documentation for
0.8.0 scoped actions remains applicable; this patch adds no new Obsidian,
AI, yazi, fzf, or onboarding functionality.
