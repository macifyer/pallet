#!/usr/bin/env python3
"""Explicit Obsidian intent routing; never infer note creation from search.

The host supplies optional scope metadata. Generic launcher queries do not
become Obsidian searches unless they name Obsidian or explicitly request a
new note. No indexing, vault selection, or CLI readiness is claimed here.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import sys
from urllib.parse import urlencode, quote


def uri(action: str, **params: str) -> str:
    query = urlencode({k: v for k, v in params.items() if v}, quote_via=quote)
    return 'obsidian://' + action + ('?' + query if query else '')


def row(key: str, title: str, subtitle: str, query: str, url: str = '', argv=None, confirm=False) -> dict:
    action = {'type': 'launch', 'title': title, 'argv': argv} if argv else {'type': 'open', 'title': title, 'url': url}
    if confirm:
        action.update(danger='confirm', tone='positive', confirmation={
            'title': 'Create this Obsidian note?',
            'detail': subtitle + ' No overwrite, append, content, or clipboard parameter is sent.',
        })
    actions = [action, {'type': 'copy', 'title': 'Copy target', 'text': ' '.join(argv) if argv else url}] if (url or argv) else []
    return {
        'id': 'obsidian:' + key, 'title': title, 'subtitle': subtitle,
        'icon': 'obsidian', 'fallbackIcon': '◆', 'fallbackColor': '#cba6f7',
        'keywords': query.lower() + ' obsidian', 'score': 0.95,
        'provider': 'obsidian', 'actions': actions,
    }


def catalog(query: str) -> list[dict]:
    launch = ['obsidian'] if shutil.which('obsidian') else ['xdg-open', uri('choose-vault')]
    return [
        row('open', 'Open Obsidian', 'Launch Obsidian', query, argv=launch),
        row('search', 'Search Obsidian', 'Open search in Obsidian; no local note index yet', query, uri('search')),
        row('daily', 'Obsidian Daily Note', "Open or create today's note; requires Daily notes in Obsidian", query, uri('daily')),
        row('vaults', 'Obsidian Vault Manager', 'Choose a vault in Obsidian', query, uri('choose-vault')),
        row('setup', 'Obsidian Setup Guide', 'URI registration instructions; not an in-palette setup screen', query, 'https://help.obsidian.md/uri'),
        row('cli-guide', 'Obsidian CLI Setup Guide', 'CLI documentation; executable presence does not prove CLI readiness', query, 'https://help.obsidian.md/cli'),
    ]


def search(query: str, scope: str = '') -> list[dict]:
    original = query.strip()
    q = original
    branded = bool(re.match(r'^obsidian(?:\s|$)', q, re.I))
    if branded:
        q = re.sub(r'^obsidian(?:\s+|$)', '', q, count=1, flags=re.I).strip()
    create = re.fullmatch(r'(?:new|create)\s+note(?:\s+(.*))?', q, flags=re.I | re.S)
    if scope != 'obsidian' and not branded and not create:
        return []
    if not q:
        return catalog(original)
    if create:
        name = (create.group(1) or '').strip()
        valid = bool(name) and len(name) <= 200 and name not in ('.', '..') and all(c.isprintable() and c not in '/\\' for c in name)
        if not valid:
            return [row('new-note-name-required', 'New Obsidian Note — enter a valid name',
                        'Use obsidian:new note NAME; one filename, no slash or control characters', original)]
        key = 'new-note-' + hashlib.sha256(name.encode()).hexdigest()[:16]
        return [row(key, 'New Obsidian Note: ' + name,
                    'Name: ' + name + '. Destination is chosen by Obsidian; Pallet vault selection is not configured.',
                    original, uri('new', name=name), confirm=True)]
    choices = catalog(original)
    command = q.casefold()
    if command in ('open', 'launch'):
        return choices[:1]
    if command in ('daily', 'today', 'daily note'):
        return choices[2:3]
    if command in ('vault', 'vaults', 'vault manager'):
        return choices[3:4]
    if command in ('setup', 'settings', 'help'):
        return choices[4:]
    if command in ('cli', 'cli help', 'cli setup'):
        return choices[5:]
    term = re.sub(r'^(?:search|find)(?:\s+|$)', '', q, count=1, flags=re.I)
    key = 'search-' + hashlib.sha256(term.encode()).hexdigest()[:16]
    return [row(key, 'Search Obsidian' + (': ' + term if term else ''),
                'Search inside Obsidian — no note will be created', original, uri('search', query=term))]


def main() -> None:
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        op = msg.get('op')
        if op == 'search':
            print(json.dumps({'id': msg.get('id', ''), 'results': search(str(msg.get('query', '')), str(msg.get('scope', '')))}), flush=True)
        elif op == 'cancel':
            print(json.dumps({'id': msg.get('target', ''), 'cancelled': True}), flush=True)
        elif op == 'execute':
            print(json.dumps({'id': msg.get('id', ''), 'executed': False}), flush=True)

if __name__ == '__main__':
    main()
