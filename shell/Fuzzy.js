// Pure logic — no Qt imports. Runnable under node for tests, following the
// pattern of MaNi4's Model.js so ranking stays testable outside the UI.
.pragma library

// Match tiers. Higher tiers always outrank lower ones; provider scores,
// intent, and recency only order results *within* a tier.
var TIER_EXACT = 5;
var TIER_PREFIX = 4;
var TIER_WORD = 3;
var TIER_SUBSTRING = 2;
var TIER_SUBSEQUENCE = 1;
var FALLBACK_RANK = -10;
// Width of one tier inside the command-intent file band: [2.0, 2.4) covers
// file substring..exact, below any command substring row (>= 2.45).
var FILE_BAND_STEP = 0.1;  // "Run: <query>" and other fallbacks: always last.

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

function isBoundary(t, i) {
    if (i === 0) return true;
    const c = t[i - 1];
    return c === " " || c === "-" || c === "_" || c === "." || c === "/" || c === ":" || c === "(" || c === "›";
}

// Initials of the words in text, e.g. "Night Light" -> "nl".
function initials(t) {
    let out = "";
    for (let i = 0; i < t.length; i++)
        if (t[i] !== " " && isBoundary(t, i)) out += t[i];
    return out;
}

// Classify how query matches one text: {tier, quality 0..1} or null.
function matchTier(query, text) {
    if (text === undefined || text === null) return null;
    const q = String(query).toLowerCase();
    const t = String(text).toLowerCase();
    if (q.length === 0 || t.length === 0) return null;
    if (t === q) return { tier: TIER_EXACT, quality: 1 };
    if (t.startsWith(q)) return { tier: TIER_PREFIX, quality: q.length / t.length };
    let at = t.indexOf(q);
    let substringAt = at;
    while (at !== -1) {
        if (isBoundary(t, at)) return { tier: TIER_WORD, quality: 0.5 + 0.5 * (1 - at / t.length) };
        at = t.indexOf(q, at + 1);
    }
    if (q.length >= 2 && q.indexOf(" ") === -1 && initials(t).startsWith(q))
        return { tier: TIER_WORD, quality: 0.4 };
    if (substringAt !== -1) return { tier: TIER_SUBSTRING, quality: 1 - substringAt / t.length };
    const sub = matchScore(q, t);
    if (sub < 0) return null;
    return { tier: TIER_SUBSEQUENCE, quality: (sub - 0.4) / 0.6 };
}

// Best match across a result's fields. Titles count fully; keyword aliases
// are matched per word (an exact alias ranks like a title prefix); subtitles
// can never lift a result above a word-boundary title match.
function bestMatch(query, r) {
    let best = null;
    function consider(m, cap, penalty) {
        if (m === null) return;
        const tier = Math.min(m.tier, cap) - penalty;
        if (best === null || tier > best.tier || (tier === best.tier && m.quality > best.quality))
            best = { tier: tier, quality: m.quality };
    }
    consider(matchTier(query, r.title), TIER_EXACT, 0);
    if (r.keywords !== undefined && r.keywords !== null) {
        const words = String(r.keywords).split(/\s+/);
        for (let i = 0; i < words.length; i++) {
            if (words[i].length === 0) continue;
            const m = matchTier(query, words[i]);
            if (m !== null && m.tier >= TIER_PREFIX) consider(m, TIER_PREFIX, m.tier === TIER_EXACT ? 0 : 0.5);
        }
        consider(matchTier(query, r.keywords), TIER_WORD, 0.25);
    }
    consider(matchTier(query, r.subtitle), TIER_SUBSTRING, 0.5);
    return best;
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

function isFallback(r) {
    return r.fallback === true || r.provider === "run";
}

// Client-side pass over merged provider results: drop non-matches, order by
// match tier (exact > prefix > word boundary > substring > subsequence), then
// within a tier blend match quality, the provider's advisory score, intent
// (files vs commands), and a bounded recency boost. Without file intent
// (no "/", "~" or "."), file rows rank below command rows that match at
// substring or better, whatever their own tier. Fallback rows such as
// "Run: <query>" always sort last. The sort is stable: ties keep the host's
// provider order.
function rank(query, results) {
    const q = String(query || "").toLowerCase().trim();
    const wantsFile = isFileIntent(q);
    const scored = [];
    for (let i = 0; i < results.length; i++) {
        const r = results[i];
        if (r === null || typeof r !== "object") continue;
        const advisory = typeof r.score === "number" ? Math.max(0, Math.min(1, r.score)) : 0;
        const out = {};
        for (const key in r)
            out[key] = r[key];
        out.order = i;
        if (isFallback(r)) {
            out.fuzzy = 0;
            out.tier = 0;
            out.rank = FALLBACK_RANK + advisory;
            scored.push(out);
            continue;
        }
        const m = bestMatch(q, r);
        if (m === null)
            continue;
        const isFile = r.provider === "files";
        let intent = 0;
        if (isExactFileQuery(q, r))
            intent = 0.2;
        else if (wantsFile)
            intent = isFile ? 0.15 : -0.15;
        else
            intent = isFile ? -0.15 : 0.15;
        const recent = typeof r.recent === "number" ? Math.max(0, Math.min(1, r.recent)) : 0;
        const within = Math.max(0, Math.min(0.99, 0.3 + 0.3 * m.quality + 0.25 * advisory + intent + 0.15 * recent));
        out.fuzzy = m.quality;
        out.tier = m.tier;
        out.rank = m.tier + within;
        if (isFile && !wantsFile && m.tier >= TIER_SUBSTRING) {
            // Command intent: file and folder rows form their own band below
            // every command row matching at substring or better (so Omarchy
            // "Config" or "Update Config: …" beat ~/.config/ghostty/config),
            // still above command subsequence matches. Inside the band the
            // usual tier order holds.
            out.rank = TIER_SUBSTRING + FILE_BAND_STEP * (m.tier - TIER_SUBSTRING) + FILE_BAND_STEP * 0.9 * within;
        }
        scored.push(out);
    }
    scored.sort(function (a, b) { return (b.rank - a.rank) || (a.order - b.order); });
    return scored;
}

// Index of the result with the same provider+id as `key`, or -1.
function keyOf(r) {
    return r ? String(r.provider || "") + "\u0000" + String(r.id || r.title || "") : "";
}

function indexOfKey(results, key) {
    if (!key) return -1;
    for (let i = 0; i < results.length; i++)
        if (keyOf(results[i]) === key) return i;
    return -1;
}
