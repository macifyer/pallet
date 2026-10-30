"""omarchy provider: parity with the installed Omarchy menu."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from timing import budget  # noqa: E402
SPEC = importlib.util.spec_from_file_location('omarchy_provider', ROOT / 'providers/omarchy/provider.py')
om = importlib.util.module_from_spec(SPEC)
sys.modules['omarchy_provider'] = om
SPEC.loader.exec_module(om)
FIXTURE = ROOT / 'tests/fixtures/omarchy/default/omarchy/omarchy-menu.jsonc'
_TMP = tempfile.TemporaryDirectory()
REAL = Path('/workspace/omarchy-src/default/omarchy/omarchy-menu.jsonc')


def catalog(user=None, answers=None):
    user_path = Path(_TMP.name) / f'user-{len(os.listdir(_TMP.name))}.jsonc'
    if user is not None:
        user_path.write_text(user, encoding='utf-8')
    calls = []
    def guards(list_):
        calls.append(list_)
        return answers(list_) if answers else {}
    c = om.Catalog(paths=lambda: (FIXTURE, user_path), guards=guards)
    c._calls = calls
    c.refresh()
    return c


def by_id(results):
    return {r['id']: r for r in results}


def answer(**wanted):
    """Guard answers keyed by item id: {'system.hibernate': {'w': False}}."""
    def run(guards):
        out = {}
        for n, tag, cond in guards:
            out[(n, tag)] = wanted.get(cond, {}).get(tag, True if tag == 'w' else False)
        return out
    return run


class ParseTests(unittest.TestCase):
    def test_jsonc_comments_trailing_commas_and_slashes_in_strings(self):
        items = om.parse_menu(FIXTURE.read_text())
        ids = [i['id'] for i in items]
        self.assertIn('url', ids)
        url = next(i for i in items if i['id'] == 'url')
        self.assertIn('https://a.example/x', url['action'])
        self.assertEqual(next(i for i in items if i['id'] == 'system')['aliases'], ['power-menu'])
        self.assertEqual(next(i for i in items if i['id'] == 'trigger.toggle.nightlight-on')['parent'], 'trigger.toggle')

    def test_user_overlay_overrides_declared_fields_only_and_appends(self):
        c = catalog(user='{"system.lock": {"label": "Lock Screen"}, "my.thing": {"label": "Mine", "action": "true"}, "my": {"label": "My"}}')
        self.assertEqual(c.items['system.lock']['label'], 'Lock Screen')
        self.assertEqual(c.items['system.lock']['action'], 'omarchy-system-lock')
        self.assertEqual(c.order[-2:], ['my.thing', 'my'])

    def test_unreachable_entries_are_skipped(self):
        ids = {r['entry']['id'] for r in catalog().rows}
        self.assertNotIn('orphan.child', ids)
        self.assertNotIn('apps.inner', ids)
        self.assertIn('system', ids)

    @unittest.skipUnless(REAL.is_file(), 'Omarchy source checkout not present')
    def test_real_menu_parses_and_shutdown_runs_its_own_command(self):
        items = om.parse_menu(REAL.read_text())
        self.assertGreater(len(items), 300)
        c = om.Catalog(paths=lambda: (REAL, None), guards=lambda g: {})
        c.refresh()
        self.assertGreater(len(c.rows), 300)
        for r in om.search(c, 'shutdown'):
            if r['id'] == 'omarchy:menu:system.shutdown':
                self.assertEqual(r['actions'][0]['type'], 'shell')
                self.assertEqual(r['actions'][0]['command'], c.items['system.shutdown']['action'])
                self.assertEqual(r['actions'][0]['danger'], 'confirm')
                break
        else:
            self.fail('shutdown not found')


class SearchTests(unittest.TestCase):
    def test_leaf_runs_the_menu_command_directly(self):
        # Same as Menu.qml runAction: the action string through bash -lc.
        c = catalog()
        r = by_id(om.search(c, 'lock'))['omarchy:menu:system.lock']
        self.assertEqual(r['actions'][0], {'type': 'shell', 'title': 'Run', 'command': 'omarchy-system-lock'})
        self.assertNotIn('danger', r['actions'][0])
        self.assertEqual(r['subtitle'], 'Omarchy › System')
        self.assertEqual(r['actions'][1], {'type': 'copy', 'title': 'Copy command', 'text': 'omarchy-system-lock'})

    def test_destructive_and_system_state_rows_confirm(self):
        c = catalog()
        for q, rid in [('shutdown', 'system.shutdown'), ('theme', 'remove.theme'), ('zed', 'install.editor.zed')]:
            c.answers, c.answers_at = {}, 1e18  # guards answered (nothing failing)
            c.answers = {(c.items[rid]['_n'], 'd'): False} if c.items[rid]['disabled'] else {}
            r = by_id(om.search(c, q))['omarchy:menu:' + rid]
            self.assertEqual(r['actions'][0].get('danger'), 'confirm', rid)
        self.assertEqual(om.confirm_for('install.package'), '')
        self.assertEqual(om.confirm_for('system.lock'), '')
        self.assertEqual(om.confirm_for('setup.reset'), 'danger')
        self.assertEqual(om.confirm_for('update.channel.edge'), 'warning')
        self.assertEqual(om.confirm_for('system.suspend-ish'), '')

    def test_contextual_titles(self):
        c = catalog()
        titles = {r['id']: r['title'] for r in om.search(c, 'firefox') + om.search(c, 'package') + om.search(c, 'theme')}
        self.assertEqual(titles['omarchy:menu:setup.default.browser.firefox'], 'Default Browser: Firefox')
        self.assertEqual(titles['omarchy:menu:install.package'], 'Install Package')
        self.assertEqual(titles['omarchy:menu:remove.theme'], 'Remove Theme')

    def test_submenus_open_the_native_menu(self):
        r = by_id(om.search(catalog(), 'editor'))['omarchy:menu:install.editor']
        self.assertTrue(r['subtitle'].startswith('Open menu: '))
        self.assertEqual(r['actions'][0]['argv'], ['omarchy-menu', 'summon', 'install.editor'])

    def test_aliases_and_extra_keywords_match(self):
        c = catalog()
        self.assertIn('omarchy:menu:system', by_id(om.search(c, 'power-menu')))
        self.assertIn('omarchy:menu:system.shutdown', by_id(om.search(c, 'power off')))


class GuardTests(unittest.TestCase):
    def test_unknown_guard_opens_parent_menu_instead_of_running(self):
        c = catalog()  # guards not evaluated yet
        r = by_id(om.search(c, 'hibernate'))['omarchy:menu:system.hibernate']
        self.assertEqual(r['actions'][0]['argv'], ['omarchy-menu', 'summon', 'system'])
        self.assertNotIn('danger', r['actions'][0])
        self.assertIn('opens in the Omarchy menu', r['subtitle'])

    def test_when_hides_and_toggle_pairs_show_one_side(self):
        c = catalog(answers=answer(**{'omarchy-toggle-nightlight --status': {'w': False},
                                      'omarchy-hibernation-available': {'w': False}}))
        c.ensure_guards(block=True)
        ids = by_id(om.search(c, 'nightlight'))
        self.assertIn('omarchy:menu:trigger.toggle.nightlight-on', ids)
        self.assertNotIn('omarchy:menu:trigger.toggle.nightlight-off', ids)
        self.assertEqual(ids['omarchy:menu:trigger.toggle.nightlight-on']['actions'][0]['command'],
                         c.items['trigger.toggle.nightlight-on']['action'])
        self.assertNotIn('omarchy:menu:system.hibernate', by_id(om.search(c, 'hibernate')))
        self.assertEqual(len(c._calls), 1)
        c.ensure_guards(block=True)
        self.assertEqual(len(c._calls), 1, 'fresh answers are reused')

    def test_disabled_rows_open_their_menu_instead_of_doing_nothing(self):
        # Installed already: Enter used to copy silently. Now it opens the
        # native submenu, where Omarchy shows the row disabled.
        c = catalog(answers=answer(**{'omarchy-pkg-present zed': {'d': True}}))
        c.ensure_guards(block=True)
        r = by_id(om.search(c, 'zed'))['omarchy:menu:install.editor.zed']
        self.assertIn('installed', r['subtitle'])
        self.assertEqual(r['actions'][0]['argv'], ['omarchy-menu', 'summon', 'install.editor'])
        self.assertEqual([a['type'] for a in r['actions']], ['launch', 'copy'])

    def test_guard_script_runs_conditions_in_bash_and_parses_answers(self):
        guards = [(0, 'w', 'true'), (1, 'w', 'false'), (2, 'd', '[[ 1 == 1 ]] # trailing comment')]
        self.assertEqual(om.run_guards(guards, timeout=10), {(0, 'w'): True, (1, 'w'): False, (2, 'd'): True})

    def test_guard_that_exits_leaves_row_unanswered(self):
        # Same as the native batch: the row stays unknown and opens its parent menu.
        out = om.run_guards([(0, 'w', 'exit 0')], timeout=10)
        self.assertEqual(out, {})

    def test_guard_timeout_returns_partial(self):
        # The slow guard always outlives the (scaled) budget; it is killed.
        out = om.run_guards([(0, 'w', 'true'), (1, 'w', 'sleep 60')], timeout=budget(1.5))
        self.assertEqual(out.get((0, 'w')), True)
        self.assertNotIn((1, 'w'), out)


class ExtrasTests(unittest.TestCase):
    def test_panels_present_and_deduped_against_menu_commands(self):
        c = catalog()
        r = by_id(om.search(c, 'bluetooth'))
        self.assertEqual(r['omarchy:panel-bluetooth']['actions'][0]['argv'], ['omarchy-shell', 'shell', 'summon', 'omarchy.bluetooth'])
        self.assertEqual(om.extras({'omarchy-shell shell summon omarchy.bluetooth'})[0]['id'] != 'omarchy:panel-bluetooth', True)

    def test_without_menu_file_only_extras(self):
        c = om.Catalog(paths=lambda: (None, Path('/nonexistent')), guards=lambda g: {})
        c.refresh()
        self.assertEqual({r['provider'] for r in om.search(c, 'network')}, {'omarchy'})
        self.assertTrue(all(not r['id'].startswith('omarchy:menu:') for r in om.search(c, 'a')))

    def test_protocol_end_to_end(self):
        env = dict(os.environ, OMARCHY_PATH=str(ROOT / 'tests/fixtures/omarchy'), HOME=tempfile.mkdtemp())
        lines = [json.dumps({'id': 'q1', 'op': 'search', 'query': 'shutdown'}), json.dumps({'id': '', 'op': 'warm'}),
                 json.dumps({'id': '', 'op': 'cancel', 'target': 'q0'})]
        proc = subprocess.run([sys.executable, str(ROOT / 'providers/omarchy/provider.py')], input='\n'.join(lines) + '\n',
                              text=True, capture_output=True, timeout=20, env=env)
        replies = [json.loads(l) for l in proc.stdout.splitlines()]
        self.assertEqual(replies[0]['id'], 'q1')
        self.assertEqual(replies[0]['results'][0]['id'], 'omarchy:menu:system.shutdown')
        self.assertEqual(replies[1], {'id': 'q0', 'cancelled': True})


if __name__ == '__main__':
    unittest.main()
