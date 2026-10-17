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
let cancels = 0, resets = 0, starts = 0, searches = 0, stopped = 0;
const root = {visible: true, filtered: ['old'], selectedIndex: 1, panelOpen: true, flashMessage: 'old', scopeLabel: 'old'};
const sandbox = {root,
    bridge: {cancel() {cancels++;}, search() {searches++;}},
    actionPanel: {reset() {resets++;}},
    flashTimer: {stop() {}, restart() {}},
    debounce: {stop() {stopped++;}, restart() {starts++;}},
    searchInput: {text: 'new'}, qsTr: s => s,
    Fuzzy: {rank(q, results) {return results;}}
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

const handler = palette.match(/onResultsReady: (\(results, scope, bare, unresolved\) => \{[\s\S]*?\n        \})\n        onHostError/);
assert(handler, 'missing result handler');
const receive = vm.runInNewContext('(' + handler[1] + ')', sandbox);
root.filtered = [];
receive(['late'], '', '', []);
assert.equal(root.filtered.length, 0);
root.visible = true;
receive(['fresh'], 'apps', '', ['files']);
assert.equal(root.filtered[0], 'fresh');
assert(root.flashMessage.includes('files'));
console.log('Query state and extracted QML JavaScript checks passed (not a native QML test)');
