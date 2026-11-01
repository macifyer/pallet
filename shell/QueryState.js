.pragma library

function create() {
    return { serial: 0, activeId: "" };
}

function begin(state) {
    state.serial += 1;
    state.activeId = "q" + state.serial;
    return state.activeId;
}

function cancel(state) {
    const previous = state.activeId;
    state.activeId = "";
    return previous;
}

function accepts(state, message) {
    return state.activeId.length > 0
        && message !== null && typeof message === "object"
        && message.id === state.activeId && Array.isArray(message.results);
}

function localBare(text, sentQuery, sentBare) {
    const t = String(text || "").trim();
    const q = String(sentQuery || "");
    const b = String(sentBare || "");
    const prefixLen = q.length - b.length;
    if (prefixLen === 0 && q === b) return t;
    if (prefixLen < 0 || q.substring(prefixLen) !== b) return null;
    const prefix = q.substring(0, prefixLen).replace(/\s+$/, "");
    return t.startsWith(prefix) ? t.substring(prefix.length).trim() : null;
}

function carryOver(previous, results, pending, final) {
    if (final || !Array.isArray(previous) || !Array.isArray(pending) || pending.length === 0)
        return results;
    const answered = {};
    for (let i = 0; i < results.length; i++) {
        const r = results[i];
        if (r !== null && typeof r === "object") answered[String(r.provider || "")] = true;
    }
    const out = results.slice();
    for (let i = 0; i < previous.length; i++) {
        const r = previous[i];
        if (r === null || typeof r !== "object") continue;
        const name = String(r.provider || "");
        if (!answered[name] && pending.indexOf(name) !== -1) out.push(r);
    }
    return out;
}
