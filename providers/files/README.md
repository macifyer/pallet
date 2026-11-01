# files provider

Searches files and directories under `$HOME`.

## Index

Built in a background thread at provider start with `fd` when installed
(`--base-directory $HOME`, directories then files, no per-entry `stat()`),
otherwise `os.walk` with the same prune list (`.git`, `node_modules`,
`__pycache__`, caches, package registries, Trash, `.config/chromium`).
Capped at 60k entries.

- **Cold start:** chunks are published while the walk runs, so the first
  query answers from whatever is indexed so far with `"partial": true`, and
  the provider sends one follow-up reply for the same id when the build
  completes (unless the query was cancelled).
- **Refresh:** after 60 s the index rebuilds in the background (also on the
  host's `warm` op when the overlay opens); the old index keeps serving until
  the new one swaps in atomically. A search never blocks on indexing.
- **Search:** each 4096-entry chunk packs its lowercase paths into one
  haystack string; candidates are the substring hits (`str.find`), narrowed
  in place while the user types forward, scored, cut to the top 48 with a
  heap, and only those are `stat()`ed for the recency nudge. Results are
  capped at 12. The provider still requires three characters.

## Ranking

Basename prefix > word prefix anywhere in the path (after `_ - / .` or a space) > basename substring > path substring; directories lose ties with
their files; files touched in the last 7 days get a small recency nudge;
deep paths are penalized slightly. Final order still belongs to the
frontend fuzzy pass.

## Primary Enter

Enter (actions[0]) targets the sensible app for the file, not the MIME
lottery:

| File kind | Primary action |
|---|---|
| Code/text (`text-*` families, scripts, .md) | Open in editor — `omarchy-launch-editor` (Omarchy's Setup › Defaults › Editor; `bin/omarchy-launch-editor`) when present, else `$VISUAL`/`$EDITOR`, GUI editors direct, terminal editors via `foot -e` |
| Markdown inside an Obsidian vault (ancestor holds `.obsidian/`) | Open in Obsidian via `obsidian://open?path=…` URI |
| Images, PDFs, audio/video, archives | xdg-open MIME default |

The generic MIME `Open` stays in the panel as a fallback for odd system
defaults (e.g. browsers claiming `text/plain`).

## All actions

| Result | Actions |
|---|---|
| File | primary (above) · Open · Open containing folder · Open terminal here · Copy path |
| Directory | Open (file manager) · Open terminal here · Copy path |

"Open terminal here" launches `xdg-terminal-exec --dir=<dir>` (Omarchy's terminal entry point, as used by `bin/omarchy-launch-terminal`), falling back to `foot --working-directory <dir>`; always raw argv.
