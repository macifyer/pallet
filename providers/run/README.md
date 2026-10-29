# run provider

## Run: <query>

Every query of 3+ characters gets one trailing `Run: <query>` row. Choosing it
opens a visible `foot` terminal (`foot -- sh -lc <query>`), after the
confirmation sheet. Pallet itself never executes search text. The row is a
`fallback`, so the frontend always ranks it below every real match.

## PATH discovery

Conservative and listing-only:

- PATH directories are listed with `os.scandir`; an entry counts when it is a
  regular file with an executable bit (one `stat`, following symlinks). A
  directory is re-listed only when its mtime changes. About 25 ms cold for
  ~800 commands, then ~0.1 ms per query; the `warm` op pre-lists.
- Nothing found is ever executed, opened or probed (no `--help`,
  `--version`, `which`, or shell).
- An exact command name (`btop`) adds **Command: btop** just above the Run
  row. `run:<prefix>` also lists up to 5 prefix matches.
- Only names matching `[A-Za-z0-9][A-Za-z0-9._+-]*` qualify; anything with a
  space, slash or other character skips discovery.
- These rows are fallbacks too (never above local matches), run the bare
  command with no arguments in a visible `foot` terminal, and require the
  confirmation sheet. History never records `run` rows.

`foot` is in Omarchy's default packages (`install/omarchy-base.packages`).
