import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('obsidian_provider', ROOT / 'providers/obsidian/provider.py')
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)

class ObsidianIntentTests(unittest.TestCase):
    def target(self, result):
        return result['actions'][0].get('url', '')

    def test_search_never_creates(self):
        for text in ('notes', 'project', 'a nonexistent note', 'Daily plans'):
            rows = provider.search(text, 'obsidian')
            self.assertEqual(len(rows), 1)
            url = urlsplit(self.target(rows[0]))
            self.assertEqual(url.netloc, 'search')
            self.assertEqual(parse_qs(url.query)['query'], [text])

    def test_unrelated_queries_do_not_leak_into_obsidian(self):
        for text in ('lock', 'install', 'notes', 'project', ''):
            self.assertEqual(provider.search(text), [])

    def test_branded_search_strips_only_the_brand(self):
        target = self.target(provider.search('obsidian project notes')[0])
        self.assertEqual(parse_qs(urlsplit(target).query)['query'], ['project notes'])

    def test_explicit_creation_preserves_name_and_confirms(self):
        name = 'My Notes & #ideas $(touch nope)'
        result = provider.search('new note ' + name, 'obsidian')[0]
        url = urlsplit(self.target(result))
        self.assertEqual(url.netloc, 'new')
        self.assertEqual(parse_qs(url.query), {'name': [name]})
        self.assertEqual(result['actions'][0]['danger'], 'confirm')
        self.assertNotIn('argv', result['actions'][0])
        self.assertEqual(self.target(provider.search('obsidian create note ' + name)[0]), self.target(result))

    def test_missing_or_invalid_names_have_no_actions(self):
        for text in ('new note', 'new note ../oops', 'new note /tmp/oops', 'new note a\\b', 'new note a\nb', 'new note ' + 'x' * 201):
            self.assertEqual(provider.search(text, 'obsidian')[0]['actions'], [])

    def test_force_search_for_command_like_note_title(self):
        result = provider.search('search new note Project', 'obsidian')[0]
        url = urlsplit(self.target(result))
        self.assertEqual(url.netloc, 'search')
        self.assertEqual(parse_qs(url.query)['query'], ['new note Project'])

    def test_catalog_and_guides_do_not_claim_cli_readiness(self):
        rows = provider.search('obsidian')
        self.assertFalse(any(urlsplit(self.target(r)).netloc == 'new' for r in rows))
        self.assertEqual(self.target(provider.search('cli', 'obsidian')[0]), 'https://help.obsidian.md/cli')

    def test_daily_stays_explicit(self):
        self.assertEqual(self.target(provider.search('daily', 'obsidian')[0]), 'obsidian://daily')
        self.assertEqual(urlsplit(self.target(provider.search('daily meeting', 'obsidian')[0])).netloc, 'search')

    def test_protocol_search_does_not_execute_any_action(self):
        result = subprocess.run([sys.executable, str(ROOT / 'providers/obsidian/provider.py')],
            input=json.dumps({'id': 't', 'op': 'search', 'scope': 'obsidian', 'query': 'notes'}) + '\n',
            text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['results'][0]['actions'][0]['url'], 'obsidian://search?query=notes')

    def run_host(self, query):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            target = root / 'providers/obsidian'
            target.mkdir(parents=True)
            shutil.copyfile(ROOT / 'src/host.py', root / 'src/host.py')
            shutil.copyfile(ROOT / 'providers/obsidian/provider.py', target / 'provider.py')
            (target / 'manifest.json').write_text(json.dumps({'name': 'obsidian', 'exec': [sys.executable, str(target / 'provider.py')]}), encoding='utf-8')
            result = subprocess.run([sys.executable, str(root / 'src/host.py')],
                input=json.dumps({'id': 't', 'op': 'search', 'query': query}) + '\n',
                text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_real_host_passes_scope_to_provider(self):
        message = self.run_host('obsidian:notes')
        self.assertEqual(message['scope'], 'obsidian')
        self.assertEqual(self.target(message['results'][0]), 'obsidian://search?query=notes')

    def test_real_host_mixed_search_does_not_suggest_note_creation(self):
        self.assertEqual(self.run_host('project')['results'], [])

    def test_real_host_explicit_create_has_confirmation(self):
        action = self.run_host('o:new note My Note')['results'][0]['actions'][0]
        self.assertEqual(action['url'], 'obsidian://new?name=My%20Note')
        self.assertEqual(action['danger'], 'confirm')

if __name__ == '__main__':
    unittest.main()
