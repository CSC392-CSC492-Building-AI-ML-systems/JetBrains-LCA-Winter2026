const express = require("express");
const { exec } = require("child_process");
const router = express.Router();
const { requireAuth } = require("../middleware/auth");

// CWE-78: OS command injection — user-supplied 'host' is concatenated directly into
// a shell command string. An attacker can inject arbitrary shell commands using
// metacharacters (e.g. "; rm -rf /", "| cat /etc/passwd").
router.post("/api/admin/ping", requireAuth, (req, res) => {
  const { host } = req.body;
  if (!host) {
    return res.status(400).json({ error: "host is required" });
  }
  exec("ping -c 1 " + host, (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ error: stderr });
    }
    return res.json({ output: stdout });
  });
});

module.exports = router;
