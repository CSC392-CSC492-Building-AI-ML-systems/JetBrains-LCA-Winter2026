const express = require("express");
const router = express.Router();
const { requireAuth } = require("../middleware/auth");

// In-memory user store for simplicity
const users = [
  { id: 1, username: "alice", email: "alice@example.com", role: "admin" },
  { id: 2, username: "bob", email: "bob@example.com", role: "user" },
  { id: 3, username: "carol", email: "carol@example.com", role: "user" },
];

// CWE-639: IDOR — user ID taken from URL parameter with no ownership check.
// Any authenticated user can access any other user's profile by changing the ID.
router.get("/api/users/:id", requireAuth, (req, res) => {
  const userId = parseInt(req.params.id, 10);
  const user = users.find((u) => u.id === userId);
  if (!user) {
    return res.status(404).json({ error: "User not found" });
  }
  return res.json(user);
});

router.get("/api/users", requireAuth, (req, res) => {
  return res.json(users.map(({ id, username }) => ({ id, username })));
});

module.exports = router;
