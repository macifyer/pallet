// Ranking checks for shell/Fuzzy.js (pure JS, run under node).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../shell/Fuzzy.js'), 'utf8').replace(/^\.pragma library\s*/m, ''), ctx);
const ids = list => Array.from(list, r => r.id);
const r = (id, title, extra = {}) => Object.assign({id, title, provider: 'apps', actions: []}, extra);

// Tiers: exact > prefix > word boundary > substring > subsequence.
let out = ctx.rank('term', [
    r('subseq', 'The Rest of My Day'),
    r('substr', 'Determinism'),
    r('word', 'Foot Terminal'),
    r('prefix', 'Terminal'),
    r('exact', 'Term'),
]);
assert.deepEqual(ids(out), ['exact', 'prefix', 'word', 'substr', 'subseq']);

// A high advisory score cannot lift a lower tier over a higher one.
out = ctx.rank('lock', [r('word', 'Screen lock', {score: 1}), r('prefix', 'Lockdown', {score: 0})]);
assert.deepEqual(ids(out), ['prefix', 'word']);

// "Run: <query>" never outranks a local match, even a weak subsequence one.
out = ctx.rank('reboot', [
    r('run', 'Run: reboot', {provider: 'run', score: 1}),
    r('weak', 'Remove boot entry'),
    r('sys', 'Reboot', {provider: 'system'}),
]);
assert.deepEqual(ids(out), ['sys', 'weak', 'run']);
// Fallback rows are kept even when nothing else matches.
out = ctx.rank('htop -d 5', [r('run', 'Run: htop -d 5', {provider: 'run'})]);
assert.deepEqual(ids(out), ['run']);
// Any provider can mark a row as a fallback.
out = ctx.rank('zz', [r('fb', 'zz fallback', {fallback: true}), r('m', 'zzz')]);
assert.deepEqual(ids(out), ['m', 'fb']);

// Stable: equal ranks keep host (provider) order.
out = ctx.rank('notes', [r('a', 'Notes'), r('b', 'Notes'), r('c', 'Notes')]);
assert.deepEqual(ids(out), ['a', 'b', 'c']);

// Exact keyword alias ranks like a title prefix; subtitle-only matches stay low.
out = ctx.rank('wifi', [
    r('sub', 'Something', {subtitle: 'wifi settings'}),
    r('alias', 'Network', {keywords: 'wifi wireless'}),
]);
assert.deepEqual(ids(out), ['alias', 'sub']);

// Initials count as a word-boundary match ("nl" -> Night Light).
out = ctx.rank('nl', [r('x', 'Only'), r('nl', 'Night Light')]);
assert.equal(out[0].id, 'nl');

// Command intent: apps beat incidental files on a plain word.
out = ctx.rank('fire', [r('file', 'fire_report.pdf', {provider: 'files'}), r('app', 'Firefox')]);
assert.deepEqual(ids(out), ['app', 'file']);
// File intent flips it, and an exact filename is always prominent.
out = ctx.rank('report.pdf', [r('app', 'report.pdf viewer'), r('file', 'report.pdf', {provider: 'files'})]);
assert.equal(out[0].id, 'file');

// Recency only reorders within a tier.
out = ctx.rank('fi', [r('a', 'Files'), r('b', 'Firefox', {recent: 1})]);
assert.deepEqual(ids(out), ['b', 'a']);
out = ctx.rank('files', [r('a', 'Files'), r('b', 'Files manager', {recent: 1})]);
assert.deepEqual(ids(out), ['a', 'b']);

// Selection helpers.
const list = ctx.rank('a', [r('1', 'a', {provider: 'x'}), r('2', 'ab', {provider: 'y'})]);
assert.equal(ctx.indexOfKey(list, ctx.keyOf({provider: 'y', id: '2'})), 1);
assert.equal(ctx.indexOfKey(list, ''), -1);
console.log('ranking checks passed');
