# Changelog

Release numbers come from the root manifest.json. This changelog starts with
0.8.1; it is not a reconstructed or retagged history of earlier commits.

## [Unreleased]

## [0.10.0]

Native-session verification on Omarchy is still pending for everything
below: it is covered by Python/Node tests and a synthetic host benchmark only,
not yet exercised in the real Quickshell overlay on Hyprland.

### Speed
- The host streams merged results as soon as the first provider answers
  (`partial`, `final`, `pending`, `failed`), then follow-ups under the same
  query id. Late providers still update the final view.
- Manifest routing hints `minQuery`/`scopedOnly`, plus more scope prefixes
  (`om:`/`menu:`, `s:`, `w:`, `m:`, `p:`, `run:`, `web:`).
- `op:warm` when the overlay opens: files, menus, apps, omarchy and run
  pre-load caches. Frontend debounce went from 80 ms to 30 ms.
- Files: background chunked index (no per-entry stat), partial cold replies,
  substring candidates with top-k selection; stat only for shown rows.
- Menus (AT-SPI): cache-first with stale-while-revalidate, walks on a
  worker thread with a 1.2 s budget; stdin never blocks. Without gi or the
  accessibility bus it answers [] instead of crashing.
- Apps: .desktop rescans happen in the background.
- Benchmark (`scripts/bench_host.py`, 60k-file synthetic home): warm
  median 105 ms → 7 ms, cold "notes" 571 ms with no file rows → first rows
  77 ms and files at 351 ms, typing "con…config" ~100 ms → 11–23 ms. With a
  1.5 s straggler provider: first rows 502 ms → 14 ms. The final/unresolved
  marker now arrives at 600 ms (merge deadline raised from 500 ms).

### Search quality
- Ranking tiers: exact > prefix > word boundary > substring > subsequence,
  stable ties. `fallback` rows (`Run:` and PATH commands) always rank last.
- Selection follows the same result while rows stream in; updates wait
  while an action panel or confirmation is open.
- Frecency: chosen results get a bounded `recent` boost within their tier
  (`$XDG_STATE_HOME/pallet/history.json`, 14-day half-life, 400 entries,
  `PALLET_HISTORY=0` disables; `Run:` commands are never recorded).

### Foundations
- Confirmation sheets are bound to the exact result id and query.
- Provider failures/timeouts are shown in the footer; action failures
  (provider `executed:false`, host-launched argv that fails to spawn) flash
  in the footer and raise an `omarchy-notification-send` notification.
- `launch` actions are spawned by the host (argv, no shell) so a missing
  command is reported.
- Conservative PATH discovery in the run provider: directory listing only,
  never executes candidates; exact name, or prefix with `run:`; confirm-gated.

### Omarchy parity and actions
- omarchy provider: every entry of Omarchy's own menu
  (`default/omarchy/omarchy-menu.jsonc` plus the user overlay), run through
  `omarchy-menu summon <id>`. `when`/`disabled` guards are evaluated in the
  background like the native menu. Hidden rows stay hidden, installed rows
  are marked, and unknown guards open the parent menu. Destructive and
  system-state entries (power, remove, reset, security, DNS, updates,
  installs) require confirmation. Shell panels (Network, Bluetooth, Audio,
  Power, Display, Calendar, World Clock, Tailscale, Weather) are included.
- system provider: key-bound controls Omarchy does not list in its menu,
  covering volume, mic, output and media-source switching, media keys,
  brightness, keyboard backlight, Bluetooth power, notifications, window
  helpers (Close All Windows confirms), time/battery and the agent picker.
  Power and update rows moved to the omarchy provider (no duplicates). The
  hibernation probe at import time was removed.
- New defaults provider (`web:`): Omarchy's default apps, TUIs and web apps
  as its keys launch them (private browser, tmux/herdr terminals, cliamp,
  btop, Signal, 1Password, Spotify, lazydocker when present, ChatGPT, Grok,
  HEY Calendar/New Email, New X Post). Also web-app searches
  (`youtube …`, `maps …`, `chatgpt …`, `grok …`, `google …`) with the text
  percent-encoded into one URL argument.
- Every provider README lists the Omarchy source file for each command.

### Changed
- The system provider no longer offers Lock/Suspend/Reboot/Shutdown/Update.
  The omarchy provider now provides them through the native menu.
- Files "open in editor" prefers `omarchy-launch-editor`; "terminal here"
  uses `xdg-terminal-exec --dir=`.

### Fixed (Omarchy VM smoke test)
- Typing no longer flickers or shows stale rows. While a query is in
  flight the previous answer is re-ranked locally against the new text
  (also when editing backwards or across a scope prefix that still
  matches); the list is only blanked for an empty query. Streamed partial
  messages keep the previous rows of providers that have not answered yet,
  so the 600 ms final message no longer reshuffles the list; the final
  message is authoritative. The re-rank now uses the query text that was
  sent for an answer, not the input text at the moment the reply landed.
  Replies for old query ids are still dropped.
- Ranking: without file intent (`/`, `~`, `.`), file and folder rows sit in
  their own band below every command row that matches at substring tier or
  better (still above weak subsequence matches; their own tier order is kept
  inside the band). "config" now lists Omarchy's Config, Update Config and
  Update Config: … rows before ~/.config/ghostty/config, and "theme" lists
  the Theme menu row before ~/.local/state/omarchy/current/theme. An
  exact-named file no longer gets a bonus over an exact-named command.
- Esc on a confirmation card (for example Shutdown) cancels it and returns
  straight to the results list instead of to the Actions panel; a second
  Esc closes the overlay.
- Timing tests no longer fail on slow machines (TCG VM): `tests/timing.py`
  scales time limits by `PALLET_TEST_TIME_SCALE` or a factor calibrated
  from Python start-up time (never below 1). The menus no-accessibility test
  keeps the provider's stdin open until it replies (closing it first lost
  the walk worker's answer whenever hyprctl reported a focused window); the
  guard-timeout test uses a scaled budget and a guard that always outlives
  it; the streaming test warms the host up first and checks the first emit
  against the slow provider's reply (fast row only, not final, `slow`
  pending, earlier than the slow reply) as well as a scaled 0.3 s bound.

## [0.9.1]

### Fixed
- Invalidate query IDs immediately on input changes, before debounce; clear
  obsolete results and reset the action panel/confirmation at the same time.
- Reject stale result messages and stop queued searches when hidden or
  dismissed. Empty scoped queries retain their actual empty bare query.
- Honor cancellation targets: an old cancel cannot cancel a newer query.
- Include slow/unavailable selected providers in `unresolved` and display
  an incomplete-results footer without changing the 500ms merge deadline.
- Fix the malformed footer JavaScript in the unshipped 0.9.1 draft.

### Tests and limits
- Add seven host/JavaScript lifecycle tests. Node also parses and exercises
  extracted QML handler JavaScript; this is not native QML validation.
- Configure Node.js in CI so JavaScript checks run rather than being skipped.
- Keep existing tests and release history intact; no tag is created here.
- Run-suggestion ranking changes, complete action-failure propagation,
  settings/onboarding, and the remaining roadmap are not included.

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
