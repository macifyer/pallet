import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('check_release', ROOT / 'scripts/check_release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

class ReleaseTests(unittest.TestCase):
    def validate(self, version='0.8.1', heading='0.8.1', tag=None, provider_version=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'manifest.json').write_text(json.dumps({'version': version}), encoding='utf-8')
            (root / 'CHANGELOG.md').write_text(f'# Changelog\n\n## [{heading}]\n', encoding='utf-8')
            if provider_version is not None:
                directory = root / 'providers/test'
                directory.mkdir(parents=True)
                (directory / 'manifest.json').write_text(json.dumps({'version': provider_version}), encoding='utf-8')
            return release.validate(root, tag)

    def test_valid(self):
        self.assertEqual(self.validate(tag='v0.8.1'), [])

    def test_bad_formats(self):
        for version in ('v0.8.1', '0.8', '6.4', '00.8.1'):
            self.assertTrue(self.validate(version=version))

    def test_mismatches(self):
        self.assertTrue(self.validate(heading='0.6.4'))
        self.assertTrue(self.validate(tag='v0.8.0'))

    def test_bundled_provider_has_no_separate_version(self):
        self.assertTrue(self.validate(provider_version='0.6.4'))

if __name__ == '__main__':
    unittest.main()
