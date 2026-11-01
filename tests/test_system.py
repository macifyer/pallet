"""system provider + omarchy extras: every command is a real Omarchy command."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
OMARCHY_BIN = Path('/workspace/omarchy-src/bin')


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


system = load('system_provider', 'providers/system/provider.py')
omarchy = load('omarchy_provider_x', 'providers/omarchy/provider.py')


class SystemProviderTests(unittest.TestCase):
    def test_ids_unique_and_argv_lists(self):
        keys = [e['key'] for e in system.ENTRIES]
        self.assertEqual(len(keys), len(set(keys)))
        for e in system.ENTRIES:
            argv = e['actions'][0]['argv']
            self.assertTrue(argv and all(isinstance(a, str) and a for a in argv), e['key'])

    def test_search_and_confirmation(self):
        top = system.search('volume')[0]
        self.assertEqual(top['actions'][0]['argv'], ['omarchy-audio-output-volume', 'raise'])
        close = {r['id']: r for r in system.search('close all')}['system:win-close-all']
        self.assertEqual(close['actions'][0]['danger'], 'confirm')
        self.assertEqual(system.search(''), [])

    def test_no_power_or_package_duplicates_of_the_menu(self):
        commands = {' '.join(e['actions'][0]['argv']) for e in system.ENTRIES}
        for dup in ('omarchy-system shutdown', 'omarchy-system reboot', 'systemctl suspend', 'omarchy-system-lock'):
            self.assertNotIn(dup, commands)

    @unittest.skipUnless(OMARCHY_BIN.is_dir(), 'Omarchy source checkout not present')
    def test_every_command_exists_in_omarchy_bin(self):
        argvs = [e['actions'][0]['argv'] for e in system.ENTRIES] + [x[4] for x in omarchy.EXTRAS]
        for argv in argvs:
            self.assertTrue((OMARCHY_BIN / argv[0]).exists(), argv)


if __name__ == '__main__':
    unittest.main()
