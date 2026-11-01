# defaults provider

Omarchy's opinionated default apps, launched exactly the way Omarchy's own
keybindings launch them, plus searches inside Omarchy's web apps. Scope with
`web:` (also `default:` / `defaults:`); unscoped queries need 2+ characters.

Apps that already ship a `.desktop` file in Omarchy (`applications/`: YouTube,
WhatsApp, HEY, X, Google Maps/Messages/Photos, Basecamp, Zoom, ...) and
packaged apps (Obsidian, Omacalc, Omawrite, LibreOffice, ...) come from the
`apps` provider and are not duplicated here.

## Apps and web apps

`helpers.lua` maps `{omarchy=X}` → `omarchy-launch-X`, `{webapp=URL}` →
`omarchy-launch-webapp URL`, `{tui=X}` → `omarchy-launch-tui X`,
`{tui=X, focus=true}` → `omarchy-launch-or-focus-tui X`.

| Row | argv | Source (Omarchy) |
|---|---|---|
| Terminal | `omarchy-launch-terminal` | `default/hypr/bindings/applications.lua` (Super+Return) |
| Browser | `omarchy-launch-browser` | `applications.lua` (Super+Shift+B) |
| Private Browser Window | `omarchy-launch-browser --private` | `applications.lua` (Super+Shift+Alt+B) |
| File Manager | `omarchy-launch-nautilus` | `applications.lua` (Super+Shift+F) |
| Editor | `omarchy-launch-editor` | `applications.lua` (Super+Shift+N) |
| Tmux Terminal | `omarchy-launch-terminal-tmux` | `applications.lua` (Super+Alt+Return) |
| Herdr Terminal | `omarchy-launch-terminal-herdr` | `applications.lua` (Super+Ctrl+Return) |
| Music | `omarchy-launch-spotify` | `applications.lua` (Super+Shift+M); offers to install Spotify if missing (`bin/omarchy-launch-spotify`) |
| Music TUI | `omarchy-launch-or-focus-tui cliamp` | `applications.lua` (Super+Shift+Alt+M); `cliamp` in `install/omarchy-base.packages` |
| Signal | `omarchy-launch-signal` | `applications.lua` (Super+Shift+G); offers to install if missing |
| Passwords | `omarchy-launch-1password` | `applications.lua` (Super+Shift+/); offers to install if missing |
| Docker | `omarchy-launch-tui omarchy-launch-docker-tui` | `applications.lua` (Super+Shift+D); shown only when `lazydocker` is on PATH (`shutil.which`, nothing is executed), as the binding is |
| Activity | `omarchy-launch-tui btop` | `default/hypr/bindings/utilities.lua` (Super+Shift+T); `btop` in base packages |
| ChatGPT | `omarchy-launch-webapp https://chatgpt.com` | `applications.lua` (Super+Shift+A) |
| Grok | `omarchy-launch-webapp https://grok.com` | `applications.lua` (Super+Shift+Alt+A) |
| Calendar (HEY) | `omarchy-launch-webapp https://app.hey.com/calendar/weeks/` | `applications.lua` (Super+Shift+C) |
| New Email (HEY) | `omarchy-launch-webapp https://app.hey.com/messages/new?display=standalone&new_window=true` | `applications.lua` (Super+Shift+Alt+E) |
| New X Post | `omarchy-launch-webapp https://x.com/compose/post` | `applications.lua` (Super+Shift+Alt+X) |

## Web-app searches

`youtube lofi`, `yt lofi`, `maps coffee`, `chatgpt …`, `gpt …`, `grok …`,
`twitter …`, `google …` / `search …` / `web …` give one search row for that
site, in any scope. `web:<text>` offers every site at once.

| Row | argv | Notes |
|---|---|---|
| Search the Web | `omarchy-launch-browser https://www.google.com/search?q=<text>` | `bin/omarchy-launch-browser` takes a URL |
| Search YouTube | `omarchy-launch-webapp https://www.youtube.com/results?search_query=<text>` | YouTube web app (`applications.lua`) |
| Search Google Maps | `omarchy-launch-webapp https://maps.google.com/?q=<text>` | Maps web app |
| Ask ChatGPT | `omarchy-launch-webapp https://chatgpt.com/?q=<text>` | ChatGPT web app |
| Ask Grok | `omarchy-launch-webapp https://grok.com/?q=<text>` | Grok web app |
| Search X | `omarchy-launch-webapp https://x.com/search?q=<text>` | X web app |

## Safety

- Every action is a fixed argv; the typed text only ever appears
  percent-encoded inside one URL argument (`-` is encoded too, because
  `omarchy-launch-browser` rewrites the substring `--private` in its args).
  Text over 300 characters or with control characters is ignored.
- Query-derived URLs never go to `omarchy-launch-or-focus*`, which `eval` the
  launch command.
- Nothing is executed at import or search time.
