"""Host streaming, routing, and action-reply behavior."""
import asyncio
import importlib.util
import json
from pathlib import Path
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from timing import budget  # noqa: E402
SPEC = importlib.util.spec_from_file_location('streaming_host', ROOT / 'src/host.py')
host_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host_module)


class FakeProvider:
    def __init__(self, name, alive=True, min_query=0, scoped_only=False):
        self.name, self.alive, self.messages = name, alive, []
        self.min_query, self.scoped_only = min_query, scoped_only
    wants = host_module.Provider.wants
    async def send(self, message):
        self.messages.append(message)
    async def ensure_running(self):
        pass


def later(host, delay, name, message):
    async def put():
        await asyncio.sleep(delay)
        await host.inbox.put((name, message))
    return asyncio.create_task(put())


class MergeStreamingTests(unittest.IsolatedAsyncioTestCase):
    def make_host(self, *providers):
        host = host_module.Host()
        host.providers = list(providers)
        emitted = []
        host.emit = emitted.append
        return host, emitted

    async def test_fast_provider_emits_before_slow_one(self):
        host, emitted = self.make_host(FakeProvider('apps'), FakeProvider('menus'))
        later(host, 0.0, 'apps', {'id': 'q', 'results': [{'title': 'Firefox'}]})
        later(host, 0.15, 'menus', {'id': 'q', 'results': [{'title': 'File'}]})
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 1.0):
            await host._merge('q', {'apps', 'menus'}, '', 'fi')
        self.assertGreaterEqual(len(emitted), 2)
        first, last = emitted[0], emitted[-1]
        self.assertFalse(first['final'])
        self.assertEqual(first['pending'], ['menus'])
        self.assertEqual(first['unresolved'], [])
        self.assertEqual([r['title'] for r in first['results']], ['Firefox'])
        self.assertTrue(last['final'])
        self.assertEqual(last['unresolved'], [])
        # Every message carries the full set so far, in provider order.
        self.assertEqual([r['provider'] for r in last['results']], ['apps', 'menus'])

    async def test_all_fast_providers_produce_one_final_message(self):
        host, emitted = self.make_host(FakeProvider('apps'), FakeProvider('system'))
        await host.inbox.put(('apps', {'id': 'q', 'results': []}))
        await host.inbox.put(('system', {'id': 'q', 'results': []}))
        await host._merge('q', {'apps', 'system'}, '', 'x')
        self.assertEqual(len(emitted), 1)
        self.assertTrue(emitted[0]['final'])

    async def test_partial_provider_replies_replace_earlier_rows(self):
        host, emitted = self.make_host(FakeProvider('files'))
        await host.inbox.put(('files', {'id': 'q', 'partial': True, 'results': [{'title': 'a'}]}))
        later(host, 0.05, 'files', {'id': 'q', 'results': [{'title': 'a'}, {'title': 'b'}]})
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 1.0):
            await host._merge('q', {'files'}, '', 'x')
        self.assertFalse(emitted[0]['final'])
        self.assertEqual(emitted[0]['pending'], ['files'])
        self.assertEqual([r['title'] for r in emitted[-1]['results']], ['a', 'b'])
        self.assertTrue(emitted[-1]['final'])

    async def test_straggler_after_deadline_refreshes_final_view(self):
        host, emitted = self.make_host(FakeProvider('apps'), FakeProvider('menus'))
        host.listening = True
        await host.inbox.put(('apps', {'id': 'q', 'results': [{'title': 'A'}]}))
        later(host, 0.12, 'menus', {'id': 'q', 'results': [{'title': 'M'}]})
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 0.05), patch.object(host_module, 'LATE_GRACE_S', 1.0):
            await host._merge('q', {'apps', 'menus'}, '', 'x')
        finals = [m for m in emitted if m['final']]
        self.assertEqual(finals[0]['unresolved'], ['menus'])
        self.assertEqual(finals[-1]['unresolved'], [])
        self.assertEqual([r['title'] for r in finals[-1]['results']], ['A', 'M'])

    async def test_no_late_listening_after_client_eof(self):
        host, emitted = self.make_host(FakeProvider('menus'))
        host.listening = False
        started = time.monotonic()
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 0.02), patch.object(host_module, 'LATE_GRACE_S', 5.0):
            await host._merge('q', {'menus'}, '', 'x')
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(len(emitted), 1)

    async def test_failed_providers_are_listed_separately(self):
        host, emitted = self.make_host(FakeProvider('apps'), FakeProvider('menus', alive=False))
        await host.inbox.put(('apps', {'id': 'q', 'results': []}))
        with patch.object(host_module, 'MERGE_TIMEOUT_S', 0.05):
            await host._merge('q', {'apps', 'menus'}, '', 'x')
        self.assertEqual(emitted[-1]['failed'], ['menus'])
        self.assertEqual(emitted[-1]['unresolved'], ['menus'])

    async def test_routing_skips_short_and_scoped_only_providers(self):
        host, _ = self.make_host(FakeProvider('apps'), FakeProvider('files', min_query=3),
                                 FakeProvider('run', min_query=3), FakeProvider('secret', scoped_only=True))
        self.assertEqual(host.route('', 'fi'), {'apps'})
        self.assertEqual(host.route('', 'fire'), {'apps', 'files', 'run'})
        self.assertEqual(host.route('files', 'f'), {'files'})
        self.assertEqual(host.route('secret', ''), {'secret'})

    async def test_execute_for_unknown_or_dead_provider_reports_failure(self):
        host, emitted = self.make_host(FakeProvider('menus', alive=False))
        await host.on_execute({'id': 'a1', 'provider': 'menus', 'action': {}})
        await host.on_execute({'id': 'a2', 'provider': 'nope', 'action': {}})
        self.assertEqual([m['executed'] for m in emitted], [False, False])
        self.assertIn('not running', emitted[0]['error'])

    async def test_provider_execute_reply_is_forwarded(self):
        host, emitted = self.make_host()
        host.on_provider_reply('windows', {'id': 'a1', 'executed': False, 'error': 'gone'})
        self.assertEqual(emitted, [{'id': 'a1', 'executed': False, 'provider': 'windows', 'error': 'gone'}])

    async def test_launch_reports_missing_command(self):
        host, emitted = self.make_host()
        await host.on_launch({'id': 'l1', 'argv': ['pallet-definitely-missing-command']})
        await host.on_launch({'id': 'l2', 'argv': 'not a list'})
        await host.on_launch({'id': 'l3', 'argv': ['true']})
        self.assertEqual([m['executed'] for m in emitted], [False, False, True])
        self.assertIn('command not found', emitted[0]['error'])

    async def test_launch_runs_detached_through_a_login_shell(self):
        # argv goes through bash -lc 'exec "$@"' (Omarchy's Util.execArgv);
        # a menu action string through bash -lc <action> (Util.execDetached).
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            host, emitted = self.make_host()
            await host.on_launch({'id': 'l1', 'argv': ['sh', '-c', f'echo "argv $$ $(ps -o sid= -p $$)" > {out}.1']})
            await host.on_launch({'id': 'l2', 'command': f'echo "cmd $0" > {out}.2 && test -n "$PATH"'})
            deadline = time.monotonic() + budget(5)
            while time.monotonic() < deadline and not (Path(f'{out}.1').exists() and Path(f'{out}.2').exists()):
                await asyncio.sleep(0.05)
            self.assertEqual([m['executed'] for m in emitted], [True, True])
            pid, sid = Path(f'{out}.1').read_text().split()[1:3]
            self.assertEqual(pid, sid, 'launched command leads its own session (survives the palette)')
            self.assertEqual(Path(f'{out}.2').read_text().strip(), 'cmd bash')

    async def test_command_that_is_not_found_in_the_shell_is_reported(self):
        host, emitted = self.make_host()
        with patch.object(host_module, 'LAUNCH_WATCH_S', budget(5)):
            await host.on_launch({'id': 'l1', 'command': 'pallet-definitely-missing-command --x'})
            deadline = time.monotonic() + budget(5)
            while time.monotonic() < deadline and len(emitted) < 2:
                await asyncio.sleep(0.05)
        self.assertEqual(emitted[0], {'id': 'l1', 'executed': True})
        self.assertEqual(emitted[1]['executed'], False)
        self.assertIn('command not found: pallet-definitely-missing-command', emitted[1]['error'])
        await host.on_launch({'id': 'l2', 'command': '   '})
        self.assertEqual(emitted[-1]['executed'], False)

    def test_launch_env_adds_omarchy_bin_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'bin').mkdir()
            with patch.dict(os.environ, {'OMARCHY_PATH': '', 'PATH': '/usr/bin'}), \
                 patch.object(host_module, 'omarchy_bin_dirs', lambda: [str(Path(tmp) / 'bin')]):
                env = host_module.launch_env()
            self.assertEqual(env['OMARCHY_PATH'], tmp)
            self.assertIn(str(Path(tmp) / 'bin'), env['PATH'].split(':'))
            self.assertEqual(env['PATH'].split(':')[0], '/usr/bin')


class ScopeTests(unittest.TestCase):
    def test_new_scopes(self):
        self.assertEqual(host_module.split_scope('om: theme'), ('omarchy', 'theme'))
        self.assertEqual(host_module.split_scope('sys:reboot'), ('system', 'reboot'))
        self.assertEqual(host_module.split_scope('w: foot'), ('windows', 'foot'))
        self.assertEqual(host_module.split_scope('web: youtube cats'), ('defaults', 'youtube cats'))
        self.assertEqual(host_module.split_scope('nope: x'), ('', 'nope: x'))


class EndToEndStreamingTest(unittest.TestCase):
    """Real subprocess host with one fast and one slow provider over pipes."""
    def test_first_results_do_not_wait_for_slow_provider(self):
        fast = "import json,sys\nfor l in sys.stdin:\n m=json.loads(l)\n if m.get('op')=='search': print(json.dumps({'id':m['id'],'results':[{'title':'fast'}]}),flush=True)\n"
        slow = "import json,sys,time\nfor l in sys.stdin:\n m=json.loads(l)\n if m.get('op')=='search':\n  time.sleep(0.4); print(json.dumps({'id':m['id'],'results':[{'title':'slow'}]}),flush=True)\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            shutil.copyfile(ROOT / 'src/host.py', root / 'src/host.py')
            for name, code in (('fast', fast), ('slow', slow)):
                d = root / 'providers' / name
                d.mkdir(parents=True)
                (d / 'w.py').write_text(code)
                (d / 'manifest.json').write_text(json.dumps({'name': name, 'exec': [sys.executable, str(d / 'w.py')]}))
            proc = subprocess.Popen([sys.executable, str(root / 'src/host.py')], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

            def run(qid):
                """Send one search; return [(seconds, msg)] up to the first message with both rows."""
                start = time.monotonic()
                proc.stdin.write(json.dumps({'id': qid, 'op': 'search', 'query': 'x'}) + '\n'); proc.stdin.flush()
                stamps = []
                while True:
                    ready, _, _ = select.select([proc.stdout], [], [], budget(3))
                    self.assertTrue(ready, 'host did not answer')
                    msg = json.loads(proc.stdout.readline())
                    if msg.get('id') != qid:
                        continue
                    stamps.append((time.monotonic() - start, msg))
                    if 'slow' in [r['title'] for r in msg['results']]:
                        return stamps
            try:
                # Warm-up: wait until both providers are up and have answered
                # once, so start-up cost is not measured as streaming latency.
                run('q0')
                stamps = run('q1')
            finally:
                proc.stdin.close(); proc.wait(timeout=budget(5)); proc.stdout.close()
        first_t, first = stamps[0]
        slow_t, last = stamps[-1]
        # The first emit carries only the fast row, is not final, and arrives
        # before the slow provider's reply: it did not wait for it.
        self.assertEqual([r['title'] for r in first['results']], ['fast'])
        self.assertIs(first['final'], False)
        self.assertEqual(first['pending'], ['slow'])
        self.assertLess(first_t, slow_t)
        self.assertLess(first_t, budget(0.3))
        self.assertEqual([r['title'] for r in last['results']], ['fast', 'slow'])
        self.assertIs(last['final'], True)


if __name__ == '__main__':
    unittest.main()
