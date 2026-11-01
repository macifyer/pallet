# system provider

Everyday controls that Omarchy binds to keys but does not list in its menu:
volume, media, brightness, keyboard backlight, Bluetooth power, notifications,
window helpers and status notifications. Power, session, update and package
actions moved to the `omarchy` provider, which runs them through
`omarchy-menu summon` with confirmations.

Every row is a fixed argv (no shell, no user input) of a command that exists in
Omarchy's `bin/`. The provider runs nothing at import or search time.

## Entries

| Entry | argv | Source (Omarchy) |
|---|---|---|
| Volume Up / Down | `omarchy-audio-output-volume raise` / `lower` | `default/hypr/bindings/media.lua` (`{audio=…}` → helpers.lua) |
| Mute Audio | `omarchy-audio-output-volume mute-toggle` | `media.lua` (XF86AudioMute) |
| Mute Microphone | `omarchy-audio-input-mute` | `media.lua` (XF86AudioMicMute) |
| Switch Audio Output | `omarchy-audio-output-switch` | `media.lua` (Shift+XF86AudioMute) |
| Switch Media Source | `omarchy-audio-source-switch` | `media.lua` (Shift+XF86AudioPlay) |
| Play / Pause, Next Track, Previous Track | `omarchy-shell media playPause` / `next` / `previous` | `media.lua` (`{ipc="media.…"}` → helpers.lua) |
| Brightness Up / Down | `omarchy-brightness-display +5%` / `5%-` | `media.lua` (`{brightness=…}` → helpers.lua) |
| Brightness Maximum / Minimum | `omarchy-brightness-display 100%` / `1%` | `bin/omarchy-brightness-display` |
| Keyboard Backlight Up / Down / Cycle | `omarchy-brightness-keyboard up` / `down` / `cycle` | `media.lua` (XF86Kbd*) |
| Bluetooth On / Off | `omarchy-bluetooth-power on` / `off` | `bin/omarchy-bluetooth-power` |
| Dismiss Notification / Dismiss All / Open Last / History | `omarchy-shell notifications dismissOne` / `dismissAll` / `invokeLast` / `showHistory` | `default/hypr/bindings/utilities.lua` (`SUPER+,` family) |
| Toggle Window Transparency | `omarchy-hyprland-window-transparency-toggle` | `utilities.lua` (`SUPER+BACKSPACE`) |
| Toggle Full Screen Desktop | `omarchy-toggle-fullscreen-desktop` | `utilities.lua` (`bind_toggle … "fullscreen-desktop"`) |
| Pop Window Out | `omarchy-hyprland-window-pop` | `default/hypr/bindings/tiling.lua` (`SUPER+O`) |
| Toggle Tiled Full Screen | `omarchy-hyprland-window-tiled-fullscreen-toggle` | `tiling.lua` (`SUPER+CTRL+F`) |
| Minimize Window | `omarchy-hyprland-window-minimize` | `tiling.lua` (`SUPER+M`) |
| Close All Windows (**confirm**, danger) | `omarchy-hyprland-window-close-all` | `tiling.lua` (`CTRL+ALT+DELETE`) |
| Show Time | `omarchy-notification-time` | `utilities.lua` (`SUPER+CTRL+ALT+T`) |
| Show Battery Remaining | `omarchy-notification-battery` | `utilities.lua` (`SUPER+CTRL+ALT+B`) |
| Pick Agent | `omarchy-agent --pick` | `utilities.lua` (`SUPER+SHIFT+CTRL+A`) |

Window actions act on the window that had focus before the palette opened
(the palette is a layer surface, not a window).

Every entry also offers "Copy command".
