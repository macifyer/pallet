// Pure logic — no Qt imports. Runnable under node for tests, following the
// pattern of MaNi4's Model.js so ranking stays testable outside the UI.
.pragma library

// Subsequence match. Returns -1 when query is not a subsequence of text,
// otherwise 0..1 (tighter, earlier matches score higher).
function matchScore(query, text) {
    if (text === undefined || text === null)
        return -1;
    const q = String(query).toLowerCase();
    const t = String(text).toLowerCase();
    if (q.length === 0)
        return 0.05;

    let qi = 0;
    let first = -1;
    let last = -1;
    for (let ti = 0; ti < t.length && qi < q.length; ti++) {
        if (t[ti] === q[qi]) {
            if (first === -1)
                first = ti;
            last = ti;
            qi++;
        }
    }
    if (qi < q.length)
        return -1;

    const span = last - first + 1;
    const tight = Math.min(1, q.length / span);
    const earliness = 1 - first / Math.max(t.length, 1);
    return 0.4 + 0.3 * tight + 0.3 * earliness;
}

// File intent is explicit: paths and extension-like queries request files.
// Ordinary terms such as "install" or "update" are command intent, even
// when similarly named files happen to exist under $HOME.
function isFileIntent(query) {
    const q = String(query || "").trim();
    return q.indexOf("/") !== -1 || q.indexOf("~") !== -1 || q.indexOf(".") !== -1;
}

function isExactFileQuery(query, result) {
    return result.provider === "files"
        && String(result.title || "").toLowerCase() === String(query || "").trim().toLowerCase();
}

// Client-side pass over merged provider results: drop non-matches, blend
// fuzzy score with the provider's advisory score (0.7 / 0.3), and sort.
// Generic queries favor actionable non-file results over incidental filename
// matches. Explicit file intent reverses that preference; exact filename
// matches are always kept prominent.
function rank(query, results) {
    const q = String(query || "").toLowerCase();
    const wantsFile = isFileIntent(q);
    const scored = [];
    for (let i = 0; i < results.length; i++) {
        const r = results[i];
        const f = matchScore(q, r.title);
        const s = matchScore(q, r.subtitle);
        const k = matchScore(q, r.keywords);
        const best = Math.max(f, s, k);
        if (best < 0)
            continue;
        const advisory = typeof r.score === "number" ? Math.max(0, Math.min(1, r.score)) : 0;
        const out = {};
        for (const key in r)
            out[key] = r[key];
        const isFile = r.provider === "files";
        let intentAdjustment = 0;
        if (isExactFileQuery(q, r))
            intentAdjustment = 0.22;
        else if (wantsFile)
            intentAdjustment = isFile ? 0.18 : -0.18;
        else
            intentAdjustment = isFile ? -0.18 : 0.18;
        out.fuzzy = best;
        out.rank = 0.7 * best + 0.3 * advisory + intentAdjustment;
        scored.push(out);
    }
    scored.sort(function (a, b) { return b.rank - a.rank; });
    return scored;
}
