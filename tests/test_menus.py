"""menus provider: cache-first, background walks, cancel, safe execute."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('menus_provider', ROOT / 'providers/menus/provider.py')
menus = importlib.util.module_from_spec(SPEC)
sys.modules['menus_provider'] = menus
SPEC.loader.exec_module(menus)


def item(label, *path, enabled=True):
    return menus.Item(list(path), label, '', enabled, False, menus.Ref(':1.1', '/' + label))


class Harness:
    def __init__(self, items, delay=0.0, window='0xabc'):
        self.sent, self.pressed, self.walks = [], [], 0
        self.items, self.delay, self.window = items, delay, window
        self.event = threading.Event()
        self.service = menus.MenuService(self.walk, self.focus, self.record, self.pressed.append)

    def walk(self, window):
        self.walks += 1
        time.sleep(self.delay)
        return list(self.items)

    def focus(self):
        return {'address': self.window, 'pid': 1, 'title': 't'} if self.window else None

    def record(self, msg):
        self.sent.append(msg)
        self.event.set()

    def wait_for(self, count, timeout=2.0):
        end = time.monotonic() + timeout
        while len(self.sent) < count and time.monotonic() < end:
            time.sleep(0.005)
        return self.sent


class MenuServiceTests(unittest.TestCase):
    def test_cold_search_answers_after_background_walk(self):
        h = Harness([item('Save', 'File'), item('Save As…', 'File'), item('Quit', 'File')], delay=0.05)
        h.service.search('q1', 'save')
        self.assertEqual(h.sent, [], 'cold search must not block or answer early')
        sent = h.wait_for(1)
        self.assertEqual(sent[0]['id'], 'q1')
        self.assertEqual([r['title'] for r in sent[0]['results']], ['Save', 'Save As…'])

    def test_warm_search_answers_from_cache_immediately(self):
        h = Harness([item('Save', 'File')])
        h.service.warm()
        time.sleep(0.05)
        started = time.monotonic()
        h.service.search('q2', 'sav')
        self.assertLess(time.monotonic() - started, 0.05)
        self.assertEqual(h.sent[-1]['id'], 'q2')
        self.assertEqual(h.walks, 1)

    def test_cancelled_cold_query_never_answers(self):
        h = Harness([item('Save', 'File')], delay=0.05)
        h.service.search('q1', 'save')
        h.service.cancel('q1')
        time.sleep(0.15)
        self.assertEqual(h.sent, [{'id': 'q1', 'cancelled': True}])

    def test_superseded_cold_query_only_newest_answers(self):
        h = Harness([item('Save', 'File')], delay=0.05)
        h.service.search('q1', 'sa')
        h.service.search('q2', 'save')
        sent = h.wait_for(1)
        time.sleep(0.05)
        self.assertEqual([m['id'] for m in h.sent], ['q2'])
        self.assertEqual(h.walks, 1, 'one walk per window at a time')

    def test_stale_cache_serves_then_revalidates(self):
        h = Harness([item('Save', 'File')])
        h.service.warm(); time.sleep(0.05)
        h.service.cache['0xabc']['at'] -= menus.CACHE_TTL + 1
        h.items = [item('Save', 'File'), item('Save All', 'File')]
        h.service.search('q3', 'save')
        self.assertEqual(len(h.sent[-1]['results']), 1)  # served stale, instantly
        time.sleep(0.05)
        h.service.search('q4', 'save')
        self.assertEqual(len(h.sent[-1]['results']), 2)

    def test_walk_failure_answers_empty(self):
        h = Harness([])
        def boom(window):
            raise RuntimeError('a11y exploded')
        h.service.walker = boom
        h.service.search('q1', 'x')
        self.assertEqual(h.wait_for(1)[0], {'id': 'q1', 'results': []})

    def test_execute_presses_matching_item_by_path_and_label(self):
        h = Harness([item('Save', 'File'), item('Quit', 'File')])
        h.service.warm(); time.sleep(0.05)
        h.service.search('q', 'quit')
        action = h.sent[-1]['results'][0]['actions'][0]
        # The tree changes order before Enter: the index is stale.
        h.service.cache['0xabc']['items'] = [item('Quit', 'File'), item('Save', 'File')]
        h.service.execute('a1', action)
        self.assertEqual(h.sent[-1], {'id': 'a1', 'executed': True})
        self.assertEqual(h.pressed[-1].path, '/Quit')

    def test_execute_refuses_other_window_or_missing_item(self):
        h = Harness([item('Quit', 'File')])
        h.service.warm(); time.sleep(0.05)
        h.service.search('q', 'quit')
        action = dict(h.sent[-1]['results'][0]['actions'][0])
        h.window = '0xother'
        h.service.execute('a1', action)
        self.assertFalse(h.sent[-1]['executed'])
        self.assertIn('no longer focused', h.sent[-1]['error'])
        h.window = '0xabc'
        h.service.execute('a2', dict(action, label='Delete Everything'))
        self.assertFalse(h.sent[-1]['executed'])
        self.assertEqual(h.pressed, [])

    def test_disabled_items_have_no_actions_and_ids_are_stable(self):
        h = Harness([item('Undo', 'Edit', enabled=False)])
        h.service.warm(); time.sleep(0.05)
        h.service.search('q', 'undo')
        first = h.sent[-1]['results'][0]
        self.assertEqual(first['actions'], [])
        h.service.search('q2', 'undo')
        self.assertEqual(h.sent[-1]['results'][0]['id'], first['id'])


class MenusWithoutGiTest(unittest.TestCase):
    def test_provider_stays_up_and_answers_without_accessibility(self):
        env = dict(os.environ, PATH='/usr/bin:/bin', DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
        code = ("import sys; sys.modules['gi'] = None\n"
                "import runpy; runpy.run_path(%r, run_name='__main__')" % str(ROOT / 'providers/menus/provider.py'))
        proc = subprocess.run([sys.executable, '-c', code], input=json.dumps({'id': 'q1', 'op': 'search', 'query': 'save'}) + '\n',
                              text=True, capture_output=True, timeout=10, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout.splitlines()[0]), {'id': 'q1', 'results': []})


if __name__ == '__main__':
    unittest.main()
