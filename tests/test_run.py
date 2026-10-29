import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('run_provider', ROOT / 'providers/run/provider.py')
run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run)


class RunProviderTests(unittest.TestCase):
    def test_fallback_flag_id_and_argv(self):
        [row] = run.search('  ls -la  ')
        self.assertTrue(row['fallback'])
        self.assertEqual(row['id'], 'run:ls -la')
        launch = row['actions'][0]
        self.assertEqual(launch['argv'], ['foot', '--', 'sh', '-lc', 'ls -la'])
        self.assertEqual(launch['danger'], 'confirm')

    def test_distinct_queries_get_distinct_ids(self):
        self.assertNotEqual(run.search('rm a')[0]['id'], run.search('rm b')[0]['id'])

    def test_short_queries_produce_nothing(self):
        self.assertEqual(run.search('ls'), [])


if __name__ == '__main__':
    unittest.main()
