"""defaults provider: Omarchy's default apps and web-app searches."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('defaults_provider', ROOT / 'providers/defaults/provider.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
OMARCHY = Path('/workspace/omarchy-src')


def titles(results):
    return [r['title'] for r in results]


class DefaultsTests(unittest.TestCase):
    def test_catalog_rows_launch_by_argv(self):
        r = d.search('private')[0]
        self.assertEqual(r['title'], 'Private Browser Window')
        self.assertEqual(r['actions'][0]['argv'], ['omarchy-launch-browser', '--private'])
        self.assertIn('Super+Shift+Alt+B', r['subtitle'])
        self.assertEqual(d.search('btop')[0]['actions'][0]['argv'], ['omarchy-launch-tui', 'btop'])

    def test_site_word_searches_with_encoded_argument(self):
        r = d.search('youtube lofi; rm -rf ~ $(x)')[0]
        argv = r['actions'][0]['argv']
        self.assertEqual(argv[0], 'omarchy-launch-webapp')
        self.assertEqual(len(argv), 2)
        self.assertTrue(argv[1].startswith('https://www.youtube.com/results?search_query='))
        tail = argv[1].split('=', 1)[1]
        for ch in ' ;$()-':
            self.assertNotIn(ch, tail)
        self.assertEqual(unquote(tail), 'lofi; rm -rf ~ $(x)')

    def test_private_flag_cannot_be_smuggled_into_browser_search(self):
        argv = d.search('google a --private b')[0]['actions'][0]['argv']
        self.assertEqual(argv[0], 'omarchy-launch-browser')
        self.assertNotIn('--private', argv[1])

    def test_search_never_uses_eval_wrappers(self):
        for q, scope in [('maps x', ''), ('chatgpt y', ''), ('anything', 'defaults')]:
            for r in d.search(q, scope):
                if r['id'].startswith('defaults:search-'):
                    self.assertNotIn('or-focus', r['actions'][0]['argv'][0])

    def test_scoped_text_offers_every_site_and_unscoped_does_not(self):
        scoped = titles(d.search('cats', 'defaults'))
        self.assertEqual(scoped[0], 'Search the Web: cats')
        self.assertIn('Search X: cats', scoped)
        self.assertEqual(d.search('cats'), [])

    def test_scoped_empty_lists_catalog_and_ids_are_stable(self):
        rows = d.search('', 'defaults')
        self.assertGreaterEqual(len(rows), 15)
        self.assertEqual(rows[0]['id'], 'defaults:terminal')
        self.assertEqual(d.search('youtube a')[0]['id'], d.search('youtube a')[0]['id'])
        self.assertNotEqual(d.search('youtube a')[0]['id'], d.search('youtube b')[0]['id'])

    def test_invalid_terms_are_ignored(self):
        self.assertEqual(d.search('youtube ' + 'a' * 400), [])
        self.assertEqual(d.search('youtube'), [])

    def test_docker_only_when_lazydocker_present(self):
        with mock.patch.object(d.shutil, 'which', return_value=None):
            self.assertNotIn('Docker', titles(d.search('docker')))
        with mock.patch.object(d.shutil, 'which', return_value='/usr/bin/lazydocker'):
            self.assertIn('Docker', titles(d.search('docker')))

    @unittest.skipUnless(OMARCHY.is_dir(), 'Omarchy source checkout not present')
    def test_every_command_is_real_and_every_webapp_url_is_omarchys(self):
        bindings = (OMARCHY / 'default/hypr/bindings/applications.lua').read_text()
        for e in d.CATALOG:
            argv = e['argv']
            self.assertTrue((OMARCHY / 'bin' / argv[0]).exists(), argv)
            if argv[0] == 'omarchy-launch-webapp':
                self.assertIn('"' + argv[1] + '"', bindings, argv)
            if argv[0] in ('omarchy-launch-tui', 'omarchy-launch-or-focus-tui') and argv[1] != 'omarchy-launch-docker-tui':
                self.assertIn(argv[1], (OMARCHY / 'install/omarchy-base.packages').read_text().split())

    def test_protocol(self):
        lines = '\n'.join(json.dumps(m) for m in [{'id': '1', 'op': 'search', 'query': 'tmux'},
                                                    {'id': '2', 'op': 'execute'}]) + '\n'
        out = subprocess.run([sys.executable, str(ROOT / 'providers/defaults/provider.py')], input=lines,
                             capture_output=True, text=True, timeout=10).stdout.splitlines()
        first, second = json.loads(out[0]), json.loads(out[1])
        self.assertEqual(first['results'][0]['id'], 'defaults:tmux')
        self.assertFalse(second['executed'])


if __name__ == '__main__':
    unittest.main()
