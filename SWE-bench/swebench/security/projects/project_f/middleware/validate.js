"use strict";
// BUG (CWE-1333): The username validation regex uses a nested quantifier pattern
// that causes catastrophic backtracking on certain inputs. An attacker can send
// a carefully crafted string like "aaaa...a!" to peg the CPU at 100% and deny
// service to other users.
const USERNAME_RE = /^([a-zA-Z0-9]+\s*)+$/;   // line 6 — ReDoS pattern

function validateUsername(username) {
    return USERNAME_RE.test(username);
}

function validateMiddleware(req, res, next) {
    const username = req.body && req.body.username;
    if (username !== undefined && !validateUsername(username)) {
        return res.status(400).json({ error: "Invalid username" });
    }
    next();
}

module.exports = { validateMiddleware, validateUsername };
