"""Frecency history: record, decay, annotate, persistence, opt-out."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('history_host', ROOT / 'src/host.py')
host_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host_module)
History = host_module.History


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state' / 'history.json'

    def test_record_annotate_and_persist(self):
        h = History(self.path, enabled=True)
        for _ in range(3):
            h.record('apps', 'apps:firefox.desktop', 'Firefox')
        rows = [{'provider': 'apps', 'id': 'apps:firefox.desktop', 'title': 'Firefox'},
                {'provider': 'apps', 'id': 'apps:foot.desktop', 'title': 'Foot'}]
        h.annotate(rows)
        self.assertGreater(rows[0]['recent'], 0)
        self.assertNotIn('recent', rows[1])
        again = History(self.path, enabled=True)
        self.assertAlmostEqual(again.score('apps', 'apps:firefox.desktop'), h.score('apps', 'apps:firefox.desktop'), places=2)

    def test_decay_and_cap(self):
        h = History(self.path, enabled=True)
        h.record('apps', 'a', now=0)
        fresh = h.score('apps', 'a', now=0)
        old = h.score('apps', 'a', now=host_module.HISTORY_HALF_LIFE_S * 4)
        self.assertLess(old, fresh / 10)
        for _ in range(20):
            h.record('apps', 'a')
        self.assertLessEqual(h.score('apps', 'a'), 1.0)

    def test_run_commands_are_never_stored(self):
        h = History(self.path, enabled=True)
        h.record('run', 'run:rm -rf ~/x', 'Run: rm -rf ~/x')
        self.assertEqual(h.entries, {})
        self.assertFalse(self.path.exists())

    def test_disabled_and_corrupt_file(self):
        h = History(self.path, enabled=False)
        h.record('apps', 'a')
        self.assertFalse(self.path.exists())
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"apps\\u0000a": "nope", "x": [1, 2]', encoding='utf-8')
        self.assertEqual(History(self.path, enabled=True).entries, {})
        self.path.write_text(json.dumps({'apps\u0000a': 'nope', 'apps\u0000b': [2, 5]}), encoding='utf-8')
        self.assertEqual(list(History(self.path, enabled=True).entries), ['apps\u0000b'])

    def test_lru_cap(self):
        h = History(self.path, enabled=True)
        for i in range(host_module.HISTORY_MAX + 5):
            h.record('files', f'f{i}', now=i)
        self.assertEqual(len(h.entries), host_module.HISTORY_MAX)
        self.assertNotIn('files\u0000f0', h.entries)


class HostRecordTests(unittest.IsolatedAsyncioTestCase):
    async def test_record_op_boosts_merged_rows(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        host = host_module.Host(History(Path(tmp.name) / 'h.json', enabled=True))
        class P:
            name, alive = 'apps', True
            async def send(self, m): pass
        host.providers = [P()]
        emitted = []; host.emit = emitted.append
        await host.on_record({'op': 'record', 'provider': 'apps', 'result': 'apps:x', 'title': 'X'})
        await host.inbox.put(('apps', {'id': 'q', 'results': [{'id': 'apps:x', 'title': 'X'}, {'id': 'apps:y', 'title': 'Y'}]}))
        await host._merge('q', {'apps'}, '', 'x')
        rows = emitted[-1]['results']
        self.assertIn('recent', rows[0])
        self.assertNotIn('recent', rows[1])


if __name__ == '__main__':
    unittest.main()
