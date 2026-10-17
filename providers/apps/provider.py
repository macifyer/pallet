#!/usr/bin/env python3
"""Discover XDG desktop applications, including Terminal=true entries.

Search never launches programs. Terminal entries use xdg-terminal-exec when
available, then supported terminal fallbacks. Executable-only tools without
desktop entries are outside this provider's scope.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import time

MAX_RESULTS = 15
MAX_DESKTOP_ACTIONS = 6
CHECK_TTL_S = 10
_apps: list[dict] = []
_checked_at = float('-inf')


def desktop_dirs() -> list[Path]:
    home = Path.home()
    user = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    if not user.is_absolute():
        user = home / '.local/share'
    system = os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share'
    roots = [user / 'applications', user / 'flatpak/exports/share/applications']
    roots += [Path(p) / 'applications' for p in system.split(':') if p and Path(p).is_absolute()]
    roots += [Path('/var/lib/flatpak/exports/share/applications'), Path('/var/lib/snapd/desktop/applications')]
    return list(dict.fromkeys(roots))


def resolves(token: str) -> bool:
    if not token:
        return False
    if '/' in token:
        return Path(token).is_absolute() and Path(token).is_file() and os.access(token, os.X_OK)
    return shutil.which(token) is not None


def split_exec(line: str, name: str = '', icon: str = '', desktop: str = '') -> list[str]:
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:
        return []
    out = []
    for token in tokens:
        if token in ('%f', '%F', '%u', '%U', '%d', '%D', '%n', '%N', '%v', '%m'):
            continue
        if token == '%i':
            if icon:
                out += ['--icon', icon]
            continue
        if token in ('%c', '%k'):
            out.append(name if token == '%c' else desktop)
            continue
        # Unknown or embedded field codes are not guessed. %% is literal %.
        if '%' in token.replace('%%', ''):
            return []
        out.append(token.replace('%%', '%'))
    return out


def terminal_argv(argv: list[str]) -> list[str] | None:
    for executable, prefix in (
        ('xdg-terminal-exec', ['xdg-terminal-exec', '--']),
        ('foot', ['foot', '--']),
        ('kitty', ['kitty', '--']),
        ('alacritty', ['alacritty', '-e']),
        ('xterm', ['xterm', '-e']),
    ):
        if shutil.which(executable):
            return prefix + argv
    return None


def parse_desktop(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    section = ''
    fields = {}
    groups = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        if section == 'Desktop Entry':
            fields.setdefault(key, value)
        elif section.startswith('Desktop Action '):
            groups.setdefault(section[15:], {}).setdefault(key, value)
    if fields.get('Type', 'Application') != 'Application':
        return None
    if any(fields.get(k, '').lower() == 'true' for k in ('Hidden', 'NoDisplay')):
        return None
    current = set(filter(None, os.environ.get('XDG_CURRENT_DESKTOP', '').split(':')))
    only = set(filter(None, fields.get('OnlyShowIn', '').split(';')))
    excluded = set(filter(None, fields.get('NotShowIn', '').split(';')))
    if (only and not current.intersection(only)) or current.intersection(excluded):
        return None
    name = fields.get('Name', '').strip()
    icon = fields.get('Icon', '')
    argv = split_exec(fields.get('Exec', ''), name, icon, str(path))
    if not name or not argv or not resolves(argv[0]):
        return None
    if fields.get('TryExec') and not resolves(fields['TryExec']):
        return None
    actions = []
    for action_id in filter(None, fields.get('Actions', '').split(';')):
        group = groups.get(action_id, {})
        title = group.get('Name', '').strip()
        command = split_exec(group.get('Exec', ''), name, icon, str(path))
        if title and command and resolves(command[0]):
            actions.append({'title': title, 'argv': command})
        if len(actions) >= MAX_DESKTOP_ACTIONS:
            break
    return {
        'name': name, 'subtitle': fields.get('GenericName') or fields.get('Comment', ''),
        'icon': icon, 'argv': argv, 'desktop_actions': actions,
        'terminal': fields.get('Terminal', '').lower() == 'true',
        'keywords': (fields.get('Keywords', '').replace(';', ' ') + ' ' + Path(argv[0]).name).lower(),
    }


def load_apps() -> list[dict]:
    seen = set()
    apps = []
    for directory in desktop_dirs():
        if not directory.is_dir():
            continue
        try:
            entries = sorted(directory.rglob('*.desktop'))
        except OSError:
            continue
        for desktop in entries:
            desktop_id = desktop.relative_to(directory).as_posix().replace('/', '-')
            if desktop_id in seen:
                continue
            # Hidden/user overrides suppress lower-priority copies too.
            seen.add(desktop_id)
            app = parse_desktop(desktop)
            if app is not None:
                app['desktop_id'] = desktop_id
                apps.append(app)
    return sorted(apps, key=lambda a: (a['name'].lower(), a['desktop_id']))


def ensure_fresh(force: bool = False) -> None:
    global _apps, _checked_at
    now = time.monotonic()
    if force or now - _checked_at >= CHECK_TTL_S:
        _apps = load_apps()
        _checked_at = now


def score(query: str, app: dict) -> float:
    name = app['name'].lower()
    if name.startswith(query):
        return 0.95
    if any(word.startswith(query) for word in name.split()):
        return 0.85
    if query in name:
        return 0.7
    if query in app['subtitle'].lower() or query in app['keywords']:
        return 0.45
    return 0.0


def actions_for(app: dict) -> list[dict]:
    def wrap(argv):
        return terminal_argv(argv) if app['terminal'] else argv
    command = wrap(app['argv'])
    if command is None:
        return []
    actions = [{'type': 'launch', 'title': 'Open in terminal' if app['terminal'] else 'Launch', 'argv': command}]
    for extra in app['desktop_actions']:
        command = wrap(extra['argv'])
        if command is not None:
            actions.append({'type': 'launch', 'title': extra['title'], 'argv': command})
    actions.append({'type': 'copy', 'title': 'Copy name', 'text': app['name']})
    return actions


def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    ensure_fresh()
    ranked = sorted(((score(q, app), app) for app in _apps), key=lambda pair: pair[0], reverse=True)
    results = []
    for rank, app in ranked:
        if rank <= 0 or len(results) >= MAX_RESULTS:
            break
        actions = actions_for(app)
        subtitle = app['subtitle']
        if app['terminal']:
            subtitle = 'Terminal application' + (' — ' + subtitle if subtitle else '')
            if not actions:
                subtitle = 'No terminal launcher available — install/configure xdg-terminal-exec or a supported terminal'
        results.append({
            'id': 'apps:' + app['desktop_id'], 'title': app['name'], 'subtitle': subtitle,
            'icon': app['icon'], 'fallbackIcon': '⌨' if app['terminal'] else '◆',
            'keywords': app['keywords'], 'score': rank, 'provider': 'apps', 'actions': actions,
        })
    return results


def main() -> None:
    ensure_fresh(force=True)
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get('op') == 'search':
            print(json.dumps({'id': msg.get('id', ''), 'results': search(str(msg.get('query', '')))}), flush=True)
        elif msg.get('op') == 'cancel':
            print(json.dumps({'id': msg.get('target', ''), 'cancelled': True}), flush=True)
        elif msg.get('op') == 'execute':
            print(json.dumps({'id': msg.get('id', ''), 'executed': False}), flush=True)

if __name__ == '__main__':
    main()
