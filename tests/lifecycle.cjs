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
    Fuzzy: fuzzyContext
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
assert.equal(root.filtered.length, 0);
assert.equal(root.panelOpen, false);
assert.equal(starts, 1);
assert.equal(searches, 0);
runSearch();
assert.equal(searches, 1);
sandbox.searchInput.text = '';
inputChanged();
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
// Editing backwards clears instead of showing stale rows.
sandbox.searchInput.text = 'xyz';
inputChanged();
assert.equal(root.filtered.length, 0);
console.log('Query state and extracted QML JavaScript checks passed (not a native QML test)');
