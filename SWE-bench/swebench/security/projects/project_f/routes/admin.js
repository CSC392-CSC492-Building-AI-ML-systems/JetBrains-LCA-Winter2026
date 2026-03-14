"use strict";
const express = require("express");
const router = express.Router();

// BUG (CWE-306): The DELETE /admin/users/:id endpoint performs a destructive
// action with no authentication check at all. Any unauthenticated request can
// delete any user record.
router.delete("/admin/users/:id", (req, res) => {   // line 8 — no auth middleware
    const userId = req.params.id;
    // Simulate deletion
    res.json({ deleted: userId });
});

router.get("/admin/stats", (req, res) => {
    // Also unprotected but read-only
    res.json({ users: 42, posts: 100 });
});

module.exports = router;
