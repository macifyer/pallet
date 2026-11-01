"""Every action-like row must do something real on Enter.

Guards against the 0.10.0 bug class: rows that list fine but whose primary
action is dead (no command, a command Omarchy does not ship, a menu route
that does not exist, or a panel/IPC target the shell does not register).
Checked against an Omarchy source checkout when one is present."""
import importlib.util
import json
from pathlib import Path
import re
import shlex
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/workspace/omarchy-src')
BIN = SRC / 'bin'
REAL_MENU = SRC / 'default/omarchy/omarchy-menu.jsonc'
HAVE_SRC = BIN.is_dir() and REAL_MENU.is_file()

# Non-Omarchy programs the stock menu runs directly (all ship with Omarchy's
# package set; see default/omarchy/omarchy-menu.jsonc).
EXTERNAL = {'systemctl', 'pkill', 'hyprpicker', 'dell-xps-touchpad-haptics', 'uwsm-app', 'xdg-terminal-exec'}
SHELL_WORDS = {'if', 'then', 'else', 'fi', 'for', 'do', 'done', 'case', 'esac', 'while', '!', '{', '}', '[[', '(('}


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


om = load('omarchy_provider_rows', 'providers/omarchy/provider.py')
system = load('system_provider_rows', 'providers/system/provider.py')


def plugin_ids():
    ids = {}
    for m in (SRC / 'shell/plugins').rglob('manifest.json'):
        data = json.loads(m.read_text())
        ids[data.get('id')] = data
    return ids


def ipc_targets():
    """target -> set of function names declared in IpcHandler blocks."""
    out = {}
    for qml in (SRC / 'shell').rglob('*.qml'):
        text = qml.read_text(errors='replace')
        for m in re.finditer(r'\b(?:IpcHandler|ShellIpc)\s*\{', text):
            depth, i = 1, m.end()
            while depth and i < len(text):
                depth += {'{': 1, '}': -1}.get(text[i], 0); i += 1
            body = text[m.end():i]
            t = re.search(r'target:\s*"([^"]+)"', body)
            if t:
                out.setdefault(t.group(1), set()).update(re.findall(r'function\s+(\w+)\s*\(', body))
    return out


def omarchy_tokens(command):
    return set(re.findall(r'(?<![\w./$-])(omarchy-[a-z0-9-]+)', command))


def first_word(command):
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        words = command.split()
    while words and (words[0] in SHELL_WORDS or re.fullmatch(r'\w+=.*', words[0])):
        words = words[1:]
    return words[0] if words else ''


def catalog_with(state):
    """Real menu with every guard forced to one state: None (unanswered),
    'pass' (every `when` true, nothing installed), 'disabled' (all installed)."""
    c = om.Catalog(paths=lambda: (REAL_MENU, None), guards=lambda g: {})
    c.refresh()
    if state is not None:
        answers = {}
        for e in c.items.values():
            if e.get('when'): answers[(e['_n'], 'w')] = True
            if e.get('disabled'): answers[(e['_n'], 'd')] = state == 'disabled'
        c.answers, c.answers_at = answers, 1e18
    return c


def all_menu_results(c):
    out = []
    for row in c.rows:
        r = om.menu_result(c, row, 1.0)
        if r is not None:
            out.append((row, r))
    return out


@unittest.skipUnless(HAVE_SRC, 'Omarchy source checkout not present')
class OmarchyMenuRowsResolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = catalog_with(None)
        cls.items = base.items
        parents = {e['parent'] for e in base.items.values()}
        cls.routes = {'root'} | {i for i, e in base.items.items()
                                 if not e['action'] and not e['target'] and (i in parents or e['provider'])}

    def check_summon(self, argv, rid):
        self.assertEqual(argv[:2], ['omarchy-menu', 'summon'], rid)
        self.assertEqual(len(argv), 3, rid)
        self.assertIn(argv[2], self.routes, f'{rid}: summons a route the menu does not have')

    def check_command(self, command, rid):
        self.assertTrue(command and command.strip(), f'{rid}: empty command')
        for tok in omarchy_tokens(command):
            self.assertTrue((BIN / tok).exists(), f'{rid}: {tok} is not an Omarchy command')
        word = first_word(command)
        compound = any(op in command for op in ('$(', '&&', '||', ';')) and omarchy_tokens(command)
        self.assertTrue((BIN / word).exists() or word in EXTERNAL or compound,
                        f'{rid}: runs {word!r}, which is neither in omarchy/bin nor a known external')

    def test_every_row_in_every_guard_state_has_a_live_primary_action(self):
        total = 0
        for state in (None, 'pass', 'disabled'):
            for row, r in all_menu_results(catalog_with(state)):
                total += 1
                rid = r['id']
                self.assertTrue(r['actions'], rid)
                a = r['actions'][0]
                self.assertIn(a['type'], ('shell', 'launch'), f'{rid}: primary action {a["type"]} does nothing visible')
                if a['type'] == 'shell':
                    self.assertFalse(row['is_menu'], rid)
                    self.assertEqual(a['command'], row['entry']['action'], f'{rid}: must run the menu\'s own action')
                    self.check_command(a['command'], rid)
                else:
                    self.check_summon(a['argv'], rid)
        self.assertGreater(total, 900)

    def test_leaves_run_their_command_and_menus_open_themselves_once_guards_pass(self):
        for row, r in all_menu_results(catalog_with('pass')):
            a = r['actions'][0]
            if row['is_menu']:
                self.assertEqual(a['argv'], ['omarchy-menu', 'summon', row['entry']['id']])
            else:
                self.assertEqual(a['type'], 'shell', r['id'])

    def test_reported_rows(self):
        results = {r['id']: r['actions'][0] for _, r in all_menu_results(catalog_with('pass'))}
        self.assertEqual(results['omarchy:menu:learn'], {'type': 'launch', 'title': 'Open in Omarchy menu',
                                                         'argv': ['omarchy-menu', 'summon', 'learn']})
        self.assertEqual(results['omarchy:menu:learn.keybindings']['command'], 'omarchy-menu-keybindings')
        self.assertEqual(results['omarchy:menu:install.aur']['command'],
                         'xdg-terminal-exec --app-id=org.omarchy.terminal omarchy-pkg-aur-install')
        # Provider-backed submenus (children generated by Menu.qml) still open.
        self.assertEqual(results['omarchy:menu:appearance.font']['argv'], ['omarchy-menu', 'summon', 'appearance.font'])

    def test_empty_submenus_are_not_listed(self):
        items = {'root': {'label': 'Go'}, 'a': {'label': 'A'}, 'b': {'label': 'B'}, 'b.x': {'label': 'X', 'action': 'true'}}
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.jsonc', delete=False) as f:
            f.write(json.dumps(items))
        try:
            c = om.Catalog(paths=lambda: (Path(f.name), None), guards=lambda g: {})
            c.refresh()
            ids = {r['entry']['id'] for r in c.rows}
            self.assertNotIn('a', ids)
            self.assertIn('b', ids)
        finally:
            Path(f.name).unlink()


@unittest.skipUnless(HAVE_SRC, 'Omarchy source checkout not present')
class ExtraAndSystemRowsResolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugins = plugin_ids()
        cls.ipc = ipc_targets()

    def check_argv(self, argv, rid):
        self.assertTrue((BIN / argv[0]).exists(), f'{rid}: {argv[0]} is not an Omarchy command')
        if argv[0] == 'omarchy-shell':
            target, method = argv[1], argv[2]
            if target == 'shell' and method in ('summon', 'toggle'):
                self.assertIn(argv[3], self.plugins, f'{rid}: no such shell plugin {argv[3]}')
                return
            self.assertIn(target, self.ipc, f'{rid}: no IpcHandler target {target}')
            self.assertIn(method, self.ipc[target], f'{rid}: {target} has no {method}()')
        if argv[0] == 'omarchy-menu' and len(argv) > 1:
            self.assertIn(argv[1], ('toggle', 'summon', 'close', 'refresh'), rid)

    def test_extras(self):
        for key, *_rest in om.EXTRAS:
            argv = _rest[3]
            self.check_argv(argv, key)
            if key.startswith('panel-'):
                kinds = self.plugins[argv[-1]].get('kinds') or [self.plugins[argv[-1]].get('kind')]
                self.assertIn('bar-widget', kinds, f'{key}: panel rows are filtered by bar layout, so must be bar widgets')

    def test_system_rows(self):
        for e in system.ENTRIES:
            a = e['actions'][0]
            self.assertEqual(a['type'], 'launch', e['key'])
            self.check_argv(a['argv'], e['key'])

    def test_reported_system_rows(self):
        found = {e['key']: e['actions'][0]['argv'] for e in system.ENTRIES}
        argvs = list(found.values())
        self.assertIn(['omarchy-notification-time'], argvs)
        self.assertIn(['omarchy-notification-battery'], argvs)


class PanelBarFilterTests(unittest.TestCase):
    def test_panels_missing_from_the_bar_are_hidden(self):
        ids = {x['id'] for x in om.extras(set(), {'omarchy.network', 'omarchy.clock'})}
        self.assertIn('omarchy:panel-network', ids)
        self.assertIn('omarchy:panel-calendar', ids)
        self.assertNotIn('omarchy:panel-tailscale', ids)
        self.assertIn('omarchy:menu', ids)  # non-panel extras always stay
        self.assertIn('omarchy:panel-tailscale', {x['id'] for x in om.extras(set(), None)})

    def test_bar_layout_parsing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'shell.json'
            p.write_text(json.dumps({'bar': {'layout': {'left': [{'id': 'omarchy.menu'}], 'right': ['omarchy.audio']}}}))
            self.assertEqual(om.bar_widget_ids(p), {'omarchy.menu', 'omarchy.audio'})
            p.write_text('not json')
            self.assertIsNone(om.bar_widget_ids(p))
            self.assertIsNone(om.bar_widget_ids(Path(tmp) / 'missing.json'))


if __name__ == '__main__':
    unittest.main()
