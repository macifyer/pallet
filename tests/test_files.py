"""files provider: background index, candidate generation, top-k, streaming."""
import importlib.util
import json
import os
from pathlib import Path
import random
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / 'providers/files/provider.py'


def load():
    spec = importlib.util.spec_from_file_location('files_provider', PROVIDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FilesIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        for rel in ('Documents/config-notes.md', 'Documents/report.pdf', 'projects/app/config.toml',
                    'projects/app/src/main.py', '.config/hypr/hyprland.conf', 'node_modules/config/index.js',
                    'deep/a/b/c/configuration.txt', 'Music/Configs Mix.mp3',
                    '.config/chromium/config-cache.json'):
            path = self.home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x')
        (self.home / 'configs').mkdir()
        self.files = load()
        self.files.HOME = self.home
        patcher = patch.object(self.files, 'fd_available', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, chunk=None):
        if chunk:
            self.files.CHUNK = chunk
        return self.files.build_index()

    def test_index_prunes_and_marks_directories(self):
        index = self.build()
        rels = {rel: d for c in index.chunks for rel, d in zip(c.rels, c.dirs)}
        self.assertTrue(index.complete)
        self.assertTrue(rels['configs'])
        self.assertFalse(rels['projects/app/config.toml'])
        self.assertNotIn('node_modules/config/index.js', rels)
        self.assertNotIn('.config/chromium/config-cache.json', rels)
        self.assertIn('.config/hypr/hyprland.conf', rels)

    def test_search_matches_naive_full_scan(self):
        self.build(chunk=3)  # many tiny chunks exercise chunk boundaries
        index = self.files._index
        all_rels = [(rel, d) for c in index.chunks for rel, d in zip(c.rels, c.dirs)]
        for q in ('conf', 'config', 'report', 'hypr', 'app/src', 'mix', 'zzz'):
            naive = sorted(((self.files.base_score(q, rel.lower(), d), rel) for rel, d in all_rels), reverse=True)
            naive = [rel for s, rel in naive if s > 0]
            got = [r['id'][len('files:'):] for r in self.files.search(q)]
            self.assertEqual(set(got), set(naive[:self.files.MAX_RESULTS]), q)

    def test_basename_prefix_ranks_first_and_topk_is_bounded(self):
        self.build()
        out = self.files.search('config')
        self.assertLessEqual(len(out), self.files.MAX_RESULTS)
        self.assertIn(out[0]['title'], {'config.toml', 'config-notes.md', 'configs', 'configuration.txt'})
        scores = [r['score'] for r in out]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_typing_forward_reuses_candidates(self):
        self.build()
        first = self.files.search('con')
        narrowed = self.files.search('confi')
        self.files._last.update(q='', version=-1, cands=None)
        fresh = self.files.search('confi')
        self.assertEqual([r['id'] for r in narrowed], [r['id'] for r in fresh])
        self.assertTrue(first)

    def test_short_query_is_ignored(self):
        self.build()
        self.assertEqual(self.files.search('co'), [])

    def test_hits_never_cross_entries(self):
        chunk = self.files.Chunk(['ab', 'cd'], [False, False])
        self.assertEqual(list(chunk.hits('b\nc')), [0])  # found, but scoring rejects it
        self.assertEqual(self.files.base_score('b\nc', 'ab', False), 0.0)
        self.assertEqual(list(chunk.hits('d')), [1])

    def test_actions_are_argv_and_use_omarchy_defaults(self):
        with patch.object(self.files.shutil, 'which', side_effect=lambda x: '/usr/bin/' + x if x in {'omarchy-launch-editor', 'xdg-terminal-exec'} else None):
            actions = self.files.actions_for('projects/app/src/main.py', False)
        self.assertEqual(actions[0]['argv'], ['omarchy-launch-editor', str(self.home / 'projects/app/src/main.py')])
        term = [a for a in actions if a['title'] == 'Open terminal here'][0]
        self.assertEqual(term['argv'], ['xdg-terminal-exec', '--dir=' + str(self.home / 'projects/app/src')])


class FilesProtocolTest(unittest.TestCase):
    def test_cold_query_answers_then_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            rng = random.Random(1)
            for i in range(3000):
                d = home / f'dir{i % 50}'
                d.mkdir(exist_ok=True)
                (d / f'note_{rng.randint(0, 99999)}_{i}.md').touch()
            (home / 'dir7' / 'needle-target.txt').touch()
            env = dict(os.environ, HOME=str(home), PATH='/usr/bin:/bin')
            proc = subprocess.Popen([sys.executable, str(PROVIDER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, env=env)
            try:
                start = time.monotonic()
                proc.stdin.write(json.dumps({'id': 'q1', 'op': 'search', 'query': 'needle'}) + '\n')
                proc.stdin.flush()
                replies = []
                while True:
                    ready, _, _ = select.select([proc.stdout], [], [], 5)
                    self.assertTrue(ready, 'files provider did not answer')
                    msg = json.loads(proc.stdout.readline())
                    replies.append(msg)
                    if not msg.get('partial'):
                        break
                self.assertLess(time.monotonic() - start, 5)
                self.assertTrue(all(m['id'] == 'q1' for m in replies))
                self.assertEqual([r['title'] for r in replies[-1]['results']], ['needle-target.txt'])
                # Warm queries after the build are not partial.
                proc.stdin.write(json.dumps({'id': 'q2', 'op': 'search', 'query': 'needle'}) + '\n')
                proc.stdin.flush()
                msg = json.loads(proc.stdout.readline())
                self.assertEqual(msg['id'], 'q2')
                self.assertNotIn('partial', msg)
            finally:
                proc.stdin.close(); proc.wait(timeout=5); proc.stdout.close()


if __name__ == '__main__':
    unittest.main()
