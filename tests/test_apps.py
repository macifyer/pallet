import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('apps_provider', ROOT / 'providers/apps/provider.py')
apps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apps)

class AppDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.user = self.root / 'user'
        self.system = self.root / 'system'
        self.environment = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.user), 'XDG_DATA_DIRS': str(self.system), 'XDG_CURRENT_DESKTOP': 'Hyprland'}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.which = patch.object(apps.shutil, 'which', side_effect=lambda x: '/fake/' + x if x in {'demo', 'other', 'xdg-terminal-exec'} else None)
        self.which.start()
        self.addCleanup(self.which.stop)
        self.roots = patch.object(apps, 'desktop_dirs', return_value=[self.user / 'applications', self.system / 'applications'])
        self.real_dirs = apps.desktop_dirs
        self.roots.start()
        self.addCleanup(self.roots.stop)
        apps._apps = []
        apps._checked_at = float('-inf')

    def desktop(self, relative='demo.desktop', fields='', system=False):
        target = (self.system if system else self.user) / 'applications' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('[Desktop Entry]\nType=Application\nName=Demo\nExec=demo %U\n' + fields, encoding='utf-8')
        return target

    def test_terminal_primary_action_uses_default_terminal_dispatcher(self):
        self.desktop(fields='Terminal=true\n')
        result = apps.search('demo')[0]
        self.assertEqual(result['actions'][0]['argv'], ['xdg-terminal-exec', '--', 'demo'])
        self.assertEqual(result['actions'][0]['title'], 'Open in terminal')

    def test_terminal_extra_action_is_also_wrapped(self):
        self.desktop(fields='Terminal=true\nActions=Extra;\n[Desktop Action Extra]\nName=Extra\nExec=other --flag\n')
        self.assertEqual(apps.search('demo')[0]['actions'][1]['argv'], ['xdg-terminal-exec', '--', 'other', '--flag'])

    def test_gui_action_stays_direct(self):
        self.desktop()
        self.assertEqual(apps.search('demo')[0]['actions'][0]['argv'], ['demo'])

    def test_terminal_fallback_and_missing_terminal(self):
        self.desktop(fields='Terminal=true\n')
        with patch.object(apps.shutil, 'which', side_effect=lambda x: '/fake/' + x if x in {'demo', 'foot'} else None):
            self.assertEqual(apps.search('demo')[0]['actions'][0]['argv'], ['foot', '--', 'demo'])
        with patch.object(apps.shutil, 'which', side_effect=lambda x: '/fake/demo' if x == 'demo' else None):
            result = apps.search('demo')[0]
            self.assertEqual(result['actions'], [])
            self.assertIn('No terminal launcher', result['subtitle'])

    def test_user_override_and_hidden_override(self):
        self.desktop(fields='Hidden=true\n')
        self.desktop(system=True)
        self.assertEqual(apps.load_apps(), [])

    def test_nested_desktop_id_is_stable_across_rename(self):
        target = self.desktop('vendor/demo.desktop')
        first = apps.load_apps()[0]['desktop_id']
        target.write_text(target.read_text().replace('Name=Demo', 'Name=Renamed'), encoding='utf-8')
        self.assertEqual(first, 'vendor-demo.desktop')
        self.assertEqual(apps.load_apps()[0]['desktop_id'], first)

    def test_identical_names_have_distinct_result_ids(self):
        self.desktop('one.desktop')
        self.desktop('two.desktop')
        self.assertEqual(len({r['id'] for r in apps.search('demo')}), 2)

    def test_visibility_and_tryexec(self):
        for fields in ('NoDisplay=true\n', 'OnlyShowIn=GNOME;\n', 'NotShowIn=Hyprland;\n', 'TryExec=missing\n'):
            target = self.desktop(fields=fields)
            self.assertIsNone(apps.parse_desktop(target))

    def test_field_codes_and_quoted_arguments(self):
        self.assertEqual(apps.split_exec('demo "two words" %F %% %c %k %i', 'Name', 'icon', '/a.desktop'),
                         ['demo', 'two words', '%', 'Name', '/a.desktop', '--icon', 'icon'])
        self.assertEqual(apps.split_exec('demo %Z'), [])
        self.assertEqual(apps.split_exec('demo "unterminated'), [])

    def test_search_does_not_interpolate_shell_syntax(self):
        target = self.desktop()
        target.write_text(target.read_text().replace('Exec=demo %U', 'Exec=demo "$(touch nope)"'), encoding='utf-8')
        self.assertEqual(apps.search('demo')[0]['actions'][0]['argv'], ['demo', '$(touch nope)'])

    def test_refresh_after_in_place_edit_and_removal(self):
        target = self.desktop()
        self.assertEqual(apps.search('demo')[0]['title'], 'Demo')
        target.write_text(target.read_text().replace('Name=Demo', 'Name=Renamed'), encoding='utf-8')
        apps.ensure_fresh(force=True)
        self.assertEqual(apps.search('renamed')[0]['title'], 'Renamed')
        target.unlink()
        apps.ensure_fresh(force=True)
        self.assertEqual(apps.search('demo'), [])

    def test_real_xdg_roots_are_absolute_ordered_and_deduplicated(self):
        roots = self.real_dirs()
        self.assertEqual(roots[0], self.user / 'applications')
        self.assertIn(self.system / 'applications', roots)
        self.assertEqual(len(roots), len(set(roots)))
        with patch.dict(os.environ, {'XDG_DATA_DIRS': 'relative:' + str(self.system) + ':' + str(self.system)}):
            self.assertTrue(all(p.is_absolute() for p in self.real_dirs()))
            self.assertEqual(self.real_dirs().count(self.system / 'applications'), 1)

if __name__ == '__main__':
    unittest.main()
