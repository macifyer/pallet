import asyncio
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('lifecycle_host', ROOT / 'src/host.py')
host_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host_module)

class FakeProvider:
    def __init__(self, name, alive=True):
        self.name, self.alive, self.messages = name, alive, []
    async def send(self, message):
        self.messages.append(message)

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def merge(self, providers, replies):
        host = host_module.Host()
        host.providers = providers
        for name, message in replies:
            await host.inbox.put((name, message))
        emitted = []
        host.emit = emitted.append
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 0.01):
            await host._merge('q1', {p.name for p in providers}, '', 'demo')
        return emitted[0]

    async def test_complete_merge_has_no_unresolved(self):
        message = await self.merge([FakeProvider('apps')], [('apps', {'id': 'q1', 'results': []})])
        self.assertEqual(message['unresolved'], [])

    async def test_slow_provider_is_reported(self):
        message = await self.merge([FakeProvider('slow')], [])
        self.assertEqual(message['unresolved'], ['slow'])

    async def test_unavailable_provider_is_reported(self):
        message = await self.merge([FakeProvider('dead', False)], [])
        self.assertEqual(message['unresolved'], ['dead'])

    async def test_stale_reply_does_not_count_as_current(self):
        message = await self.merge([FakeProvider('apps')], [('apps', {'id': 'old', 'results': []})])
        self.assertEqual(message['unresolved'], ['apps'])

    async def test_stale_cancel_cannot_cancel_new_query(self):
        host = host_module.Host()
        host.latest_qid = 'new'
        host.merge_task = asyncio.create_task(asyncio.sleep(5))
        try:
            await host.on_cancel({'target': 'old'})
            self.assertFalse(host.merge_task.cancelled())
            self.assertFalse(host.merge_task.done())
            self.assertEqual(host.latest_qid, 'new')
        finally:
            host.merge_task.cancel()
            try:
                await host.merge_task
            except asyncio.CancelledError:
                pass

    async def test_matching_cancel_clears_query(self):
        host = host_module.Host()
        provider = FakeProvider('apps')
        host.providers = [provider]
        host.latest_qid = 'q1'
        task = asyncio.create_task(asyncio.sleep(5))
        host.merge_task = task
        await host.on_cancel({'target': 'q1'})
        self.assertTrue(task.cancelled())
        self.assertIsNone(host.latest_qid)
        self.assertIsNone(host.merge_task)
        self.assertEqual(provider.messages[-1]['target'], 'q1')

class JavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for JavaScript lifecycle checks')
    def test_query_state_and_extracted_ui_javascript(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/lifecycle.cjs')],
                                cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for JavaScript ranking checks')
    def test_ranking_tiers_and_fallbacks(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/ranking.cjs')],
                                cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == '__main__':
    unittest.main()
