import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pallet_host", ROOT / "src/host.py")
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)

WORKER = """import json, sys, time
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get('op') == 'search':
        time.sleep(0.05)
        print(json.dumps({'id': msg['id'], 'results': [{'title': msg['query'], 'actions': []}]}), flush=True)
"""

class HostTests(unittest.TestCase):
    def test_scopes(self):
        for prefix, expected in host.SCOPES.items():
            self.assertEqual(host.split_scope(prefix + ': notes'), (expected, 'notes'))
        self.assertEqual(host.split_scope('https://example.com'), ('', 'https://example.com'))
        self.assertEqual(host.split_scope('files:'), ('files', ''))

    def run_host(self, messages, worker=WORKER):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            shutil.copyfile(ROOT / 'src/host.py', root / 'src/host.py')
            for name in ('obsidian', 'apps'):
                directory = root / 'providers' / name
                directory.mkdir(parents=True)
                (directory / 'worker.py').write_text(worker, encoding='utf-8')
                (directory / 'manifest.json').write_text(json.dumps({
                    'name': name, 'exec': [sys.executable, str(directory / 'worker.py')]
                }), encoding='utf-8')
            proc = subprocess.run(
                [sys.executable, str(root / 'src/host.py')],
                input=''.join(json.dumps(m) + '\n' for m in messages),
                text=True, capture_output=True, timeout=5,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return [json.loads(line) for line in proc.stdout.splitlines()]

    def test_eof_preserves_final_scoped_response(self):
        messages = self.run_host([{'id': 't', 'op': 'search', 'query': 'obsidian:notes'}])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['id'], 't')
        self.assertEqual(messages[0]['scope'], 'obsidian')
        self.assertEqual(messages[0]['bare'], 'notes')
        self.assertEqual([r['provider'] for r in messages[0]['results']], ['obsidian'])

    def test_latest_query_wins_at_eof(self):
        messages = self.run_host([
            {'id': 'old', 'op': 'search', 'query': 'obsidian:old'},
            {'id': 'new', 'op': 'search', 'query': 'apps:new'},
        ])
        self.assertEqual(messages[-1]['id'], 'new')
        self.assertEqual(messages[-1]['bare'], 'new')
        self.assertEqual([r['provider'] for r in messages[-1]['results']], ['apps'])

    def test_slow_provider_still_returns_at_deadline(self):
        messages = self.run_host([{'id': 't', 'op': 'search', 'query': 'obsidian:notes'}],
                                 'import time; time.sleep(10)')
        self.assertEqual(messages[0]['id'], 't')
        self.assertEqual(messages[0]['results'], [])

if __name__ == '__main__':
    unittest.main()
