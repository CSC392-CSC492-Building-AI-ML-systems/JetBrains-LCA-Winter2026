"use strict";
const express = require("express");
const router = express.Router();

router.get("/login", (req, res) => {
    // BUG (CWE-601): The `next` query parameter is passed directly to
    // res.redirect() without validation. An attacker can craft a URL like
    // /login?next=https://evil.com to redirect users to a phishing site
    // after login.
    const next = req.query.next || "/dashboard";
    res.redirect(next);   // line 11 — open redirect, no origin check
});

router.post("/logout", (req, res) => {
    res.json({ message: "Logged out" });
});

module.exports = router;
