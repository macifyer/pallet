import importlib.util
from pathlib import Path
import os
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('run_provider', ROOT / 'providers/run/provider.py')
run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run)


class RunProviderTests(unittest.TestCase):
    def test_fallback_flag_id_and_argv(self):
        [row] = run.search('  ls -la  ', index=run.PathIndex(''))
        self.assertTrue(row['fallback'])
        self.assertEqual(row['id'], 'run:ls -la')
        launch = row['actions'][0]
        self.assertEqual(launch['argv'], ['foot', '--', 'sh', '-lc', 'ls -la'])
        self.assertEqual(launch['danger'], 'confirm')

    def test_distinct_queries_get_distinct_ids(self):
        self.assertNotEqual(run.search('rm a')[0]['id'], run.search('rm b')[0]['id'])

    def test_short_queries_produce_nothing(self):
        self.assertEqual(run.search('ls'), [])


class PathDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.marker = os.path.join(self.dir.name, 'ran')
        for name, mode in [('btop', 0o755), ('btop-helper', 0o755), ('notexec', 0o644)]:
            path = os.path.join(self.dir.name, name)
            with open(path, 'w') as f:
                f.write('#!/bin/sh\ntouch ' + self.marker + '\n')
            os.chmod(path, mode)
        os.mkdir(os.path.join(self.dir.name, 'btopdir'))
        self.index = run.PathIndex(self.dir.name + os.pathsep + 'relative/dir')

    def test_exact_name_offers_confirmed_command_above_run_row(self):
        rows = run.search('btop', index=self.index)
        self.assertEqual([r['id'] for r in rows], ['run:cmd:btop', 'run:btop'])
        cmd = rows[0]
        self.assertTrue(cmd['fallback'])
        self.assertGreater(cmd['score'], rows[1]['score'])
        self.assertEqual(cmd['actions'][0]['argv'], ['foot', '--', 'btop'])
        self.assertEqual(cmd['actions'][0]['danger'], 'confirm')

    def test_prefix_matches_only_when_scoped_and_only_executable_files(self):
        self.assertEqual([r['id'] for r in run.search('bto', index=self.index)], ['run:bto'])
        ids = [r['id'] for r in run.search('bto', 'run', index=self.index)]
        self.assertEqual(ids, ['run:cmd:btop', 'run:cmd:btop-helper', 'run:bto'])
        self.assertEqual(run.search('notexec', index=self.index)[0]['id'], 'run:notexec')

    def test_discovery_never_executes_anything(self):
        run.search('btop', 'run', index=self.index)
        self.assertFalse(os.path.exists(self.marker))

    def test_rescans_when_directory_changes(self):
        self.assertNotIn('newtool', self.index.names())
        path = os.path.join(self.dir.name, 'newtool')
        open(path, 'w').close(); os.chmod(path, 0o755)
        st = os.stat(self.dir.name)
        os.utime(self.dir.name, (st.st_atime, st.st_mtime + 5))
        self.assertIn('newtool', self.index.names())

    def test_queries_with_spaces_or_odd_characters_skip_discovery(self):
        self.assertEqual([r['id'] for r in run.search('btop --x', 'run', index=self.index)], ['run:btop --x'])
        self.assertEqual([r['id'] for r in run.search('../btop', 'run', index=self.index)], ['run:../btop'])


if __name__ == '__main__':
    unittest.main()
