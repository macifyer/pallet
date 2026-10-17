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
