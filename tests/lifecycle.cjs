const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const rootPath = path.resolve(__dirname, '..');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(rootPath, 'shell/QueryState.js'), 'utf8').replace(/^\.pragma library\s*/, ''), context);
const state = context.create();
const first = context.begin(state);
assert(context.accepts(state, {id: first, results: []}));
context.cancel(state);
assert(!context.accepts(state, {id: first, results: []}));
const second = context.begin(state);
assert.notEqual(first, second);
assert(!context.accepts(state, {id: first, results: []}));
assert(!context.accepts(state, {id: second, results: 'invalid'}));
assert(context.accepts(state, {id: second, results: []}));
context.cancel(state);
assert(!context.accepts(state, {id: '', results: []}));

const palette = fs.readFileSync(path.join(rootPath, 'shell/PaletteWindow.qml'), 'utf8');
const fuzzyContext = {};
vm.createContext(fuzzyContext);
vm.runInContext(fs.readFileSync(path.join(rootPath, 'shell/Fuzzy.js'), 'utf8').replace(/^\.pragma library\s*/m, ''), fuzzyContext);
let cancels = 0, resets = 0, starts = 0, searches = 0, stopped = 0;
const root = {visible: true, filtered: ['old'], selectedIndex: 1, panelOpen: true, flashMessage: 'old', scopeLabel: 'old',
    statusText: '', userMoved: false, lastRaw: [], lastQuery: '', lastBare: '', deferredUpdate: null};
const sandbox = {root,
    bridge: {cancel() {cancels++;}, search() {searches++;}},
    actionPanel: {reset() {resets++;}},
    flashTimer: {stop() {}, restart() {}},
    debounce: {stop() {stopped++;}, restart() {starts++;}},
    searchInput: {text: 'new'}, qsTr: s => s,
    Fuzzy: fuzzyContext, QueryState: context
};
function method(name) {
    const match = palette.match(new RegExp('function ' + name + '\\(\\): void \\{([\\s\\S]*?)\\n    \\}'));
    assert(match, 'missing QML method: ' + name);
    return vm.runInNewContext('(function() {' + match[1] + '\n})', sandbox);
}
root.invalidateSearch = method('invalidateSearch');
const inputChanged = method('inputChanged');
const runSearch = method('runSearch');
inputChanged();
assert.equal(cancels, 1);
assert.equal(resets, 1);
// Nothing to re-rank yet: the rows already shown stay until the answer lands.
assert.deepEqual(root.filtered, ['old']);
assert.equal(root.panelOpen, false);
assert.equal(starts, 1);
assert.equal(searches, 0);
runSearch();
assert.equal(searches, 1);
sandbox.searchInput.text = '';
inputChanged();
assert.equal(root.filtered.length, 0, 'an empty query blanks the list');
assert.equal(starts, 1);
root.visible = false;
sandbox.searchInput.text = 'hidden';
inputChanged(); runSearch();
assert.equal(starts, 1);
assert.equal(searches, 1);
assert(stopped > 0);

const handler = palette.match(/onResultsReady: (\(results, scope, bare, unresolved, meta\) => \{[\s\S]*?\n        \})\n        onHostError/);
assert(handler, 'missing result handler');
const receive = vm.runInNewContext('(' + handler[1] + ')', sandbox);
const row = (provider, id, title) => ({provider, id, title, actions: [{type: 'copy', text: id}]});
root.filtered = [];
receive([row('apps', 'late', 'late')], '', 'late', [], {final: true, pending: [], failed: [], incremental: false});
assert.equal(root.filtered.length, 0, 'results ignored while hidden');
root.visible = true;
sandbox.searchInput.text = 'fresh';
receive([row('apps', 'fresh', 'fresh')], 'apps', 'fresh', ['files'], {final: true, pending: [], failed: [], incremental: false});
assert.equal(root.filtered[0].id, 'fresh');
assert(root.flashMessage.includes('files'));
// Old single-message hosts send no meta: treated as final.
receive([row('apps', 'fresh', 'fresh')], 'apps', 'fresh', [], undefined);
assert.equal(root.filtered[0].id, 'fresh');
assert.equal(root.statusText, '');

// Streaming: a partial emit, then a follow-up under the same id.
root.flashMessage = '';
sandbox.searchInput.text = 'fire';
receive([row('apps', 'b', 'firewall'), row('apps', 'c', 'fire drill')], '', 'fire', [],
    {final: false, pending: ['files'], failed: [], incremental: false});
assert.equal(root.statusText, 'searching…');
assert.equal(root.selectedIndex, 0);
// The user moves to "fire drill"; a better straggler arrives and ranks first.
root.selectedIndex = 1; root.userMoved = true;
const selected = root.filtered[1].id;
receive([row('apps', 'b', 'firewall'), row('apps', 'c', 'fire drill'), row('files', 'a', 'fire')], '', 'fire', [],
    {final: true, pending: [], failed: [], incremental: true});
assert.equal(root.filtered[0].id, 'a', 'exact match ranks first');
assert.equal(root.filtered[root.selectedIndex].id, selected, 'selection follows the same result');
assert.equal(root.statusText, '');
// Without user movement the top row stays selected.
root.userMoved = false; root.selectedIndex = 0;
receive([row('apps', 'b', 'firewall')], '', 'fire', [], {final: true, pending: [], failed: [], incremental: true});
assert.equal(root.selectedIndex, 0);
// While the action panel is open, follow-ups are deferred, never applied.
root.panelOpen = true;
const before = root.filtered;
receive([row('apps', 'z', 'fire z')], '', 'fire', [], {final: true, pending: [], failed: [], incremental: true});
assert.equal(root.filtered, before);
assert(root.deferredUpdate !== null);
root.panelOpen = false; root.deferredUpdate = null;
// Failed vs slow providers are reported separately.
receive([], '', 'fire', ['menus', 'files'], {final: true, pending: [], failed: ['menus'], incremental: false});
assert(root.flashMessage.includes('unavailable: menus'));
assert(root.flashMessage.includes('no reply from: files'));

// Typing forward re-ranks the previous answer instantly (still cancelled).
root.visible = true; root.flashMessage = '';
sandbox.searchInput.text = 'fir';
receive([row('apps', 'b', 'firewall'), row('apps', 'c', 'first aid')], '', 'fir', [], {final: true, pending: [], failed: [], incremental: false});
const cancelsBefore = cancels;
sandbox.searchInput.text = 'fire';
inputChanged();
assert.equal(cancels, cancelsBefore + 1);
assert.deepEqual(Array.from(root.filtered, r => r.id), ['b']);
assert.equal(root.panelOpen, false);
// Editing backwards re-ranks the same answer against the shorter text.
sandbox.searchInput.text = 'fi';
inputChanged();
assert.deepEqual(Array.from(root.filtered, r => r.id), ['b', 'c']);
// Nothing in the last answer matches: keep what is shown, never blank.
sandbox.searchInput.text = 'xyz';
inputChanged();
assert.deepEqual(Array.from(root.filtered, r => r.id), ['b', 'c']);
assert.equal(root.statusText, 'searching…');

// localBare follows scope prefixes of the query the answer was for.
assert.equal(context.localBare(' conf ', 'con', 'con'), 'conf');
assert.equal(context.localBare('f: conf', 'f: con', 'con'), 'conf');
assert.equal(context.localBare('f:conf', 'f: con', 'con'), 'conf');
assert.equal(context.localBare('a: conf', 'f: con', 'con'), null);
assert.equal(context.localBare('co', '', ''), 'co');
// carryOver keeps pending providers' previous rows until the final message.
const prev = [row('files', 'f1', 'config'), row('omarchy', 'o1', 'Config'), row('menus', 'm1', 'Configure')];
let merged = context.carryOver(prev, [row('omarchy', 'o2', 'Config again')], ['files', 'menus'], false);
assert.deepEqual(Array.from(merged, r => r.id), ['o2', 'f1', 'm1']);
merged = context.carryOver(prev, [row('files', 'f2', 'config.bak')], ['files'], false);
assert.deepEqual(Array.from(merged, r => r.id), ['f2'], 'a provider that answered (even partially) is not carried');
merged = context.carryOver(prev, [row('omarchy', 'o2', 'x')], ['files'], true);
assert.deepEqual(Array.from(merged, r => r.id), ['o2'], 'final messages are authoritative');

// Typing "con" -> "conf" -> "config": no blank frame, no stale rows after an
// answer, stale ids dropped, and the final view is not reshuffled by
// providers that answered late.
const bridgeState = context.create();
let sent = null;
sandbox.bridge.search = q => { sent = {id: context.begin(bridgeState), q}; };
sandbox.bridge.cancel = () => { cancels++; context.cancel(bridgeState); };
function hostReply(id, q, results, pending) {
    const msg = {id, results};
    if (!context.accepts(bridgeState, msg)) return false;
    receive(results, '', q, [], {final: pending.length === 0, pending, failed: [], incremental: false, query: q});
    return true;
}
root.lastRaw = []; root.lastQuery = ''; root.lastBare = ''; root.filtered = [];
const omarchy = [row('omarchy', 'cfg', 'Config'), row('omarchy', 'upd', 'Update Config: Tmux')];
const files = [row('files', 'gh', 'config'), row('files', 'dot', '.config')];
const apps = [row('apps', 'cons', 'Console')];
sandbox.searchInput.text = 'con'; inputChanged(); runSearch();
const conId = sent.id;
assert(hostReply(conId, 'con', omarchy.concat(apps), ['files']));
assert(hostReply(conId, 'con', omarchy.concat(files, apps), []));
const conRows = Array.from(root.filtered, r => r.id);
sandbox.searchInput.text = 'conf'; inputChanged();
assert(root.filtered.length > 0, 'no blank frame while "conf" is in flight');
assert(!Array.from(root.filtered, r => r.id).includes('cons'), 'local re-rank drops rows that no longer match');
assert(!hostReply(conId, 'con', apps, []), 'a stale reply for the old id is dropped');
runSearch();
const confId = sent.id;
// The fast provider answers first; files is still pending and keeps its rows.
assert(hostReply(confId, 'conf', omarchy, ['files']));
assert.deepEqual(Array.from(root.filtered, r => r.provider).sort(), ['files', 'files', 'omarchy', 'omarchy']);
assert(hostReply(confId, 'conf', omarchy.concat(files), []));
const confFinal = Array.from(root.filtered, r => r.id);
sandbox.searchInput.text = 'config'; inputChanged();
const configLocal = Array.from(root.filtered, r => r.id);
assert.deepEqual(configLocal.slice().sort(), confFinal.slice().sort(), 'same rows, re-ranked for "config"');
runSearch();
assert(hostReply(sent.id, 'config', omarchy, ['files']));
assert.deepEqual(Array.from(root.filtered, r => r.id), configLocal, 'partial merge does not reorder');
assert(hostReply(sent.id, 'config', omarchy.concat(files), []));
assert.deepEqual(Array.from(root.filtered, r => r.id), configLocal, 'final does not reorder');
assert.equal(root.lastQuery, 'config');
assert.notDeepEqual(conRows, []);
console.log('Query state and extracted QML JavaScript checks passed (not a native QML test)');
