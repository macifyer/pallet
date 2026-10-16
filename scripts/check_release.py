#!/usr/bin/env python3
"""Validate the single release version; never updates files or creates tags."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys

VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")

def validate(root, tag=None):
    errors = []
    try:
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        version = manifest['version']
    except (OSError, ValueError, KeyError) as exc:
        return [f'manifest.json: {exc}']
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        errors.append('manifest.version must be MAJOR.MINOR.PATCH, without v or leading zeroes')
    if tag is not None and tag != f'v{version}':
        errors.append(f'tag {tag!r} must match manifest version v{version}')
    try:
        changelog = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
        released = re.findall(r'^## \[([^\]]+)\]', changelog, flags=re.MULTILINE)
        released = [v for v in released if v != 'Unreleased']
        if not released or released[0] != version:
            errors.append('first released CHANGELOG heading must match manifest.version')
    except OSError as exc:
        errors.append(f'CHANGELOG.md: {exc}')
    for path in sorted((root / 'providers').glob('*/manifest.json')):
        try:
            provider = json.loads(path.read_text(encoding='utf-8'))
            if 'version' in provider:
                errors.append(f'{path.relative_to(root)}: bundled providers inherit the root release version')
        except (OSError, ValueError) as exc:
            errors.append(f'{path.relative_to(root)}: {exc}')
    for directory in ('src', 'providers', 'scripts', 'tests'):
        for path in sorted((root / directory).rglob('*.py')):
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as exc:
                errors.append(f'{path.relative_to(root)}: {exc}')
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='release tag to compare with manifest.version')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = validate(root, args.tag)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Release metadata and Python syntax checks passed')
    return 0

if __name__ == '__main__':
    sys.exit(main())
