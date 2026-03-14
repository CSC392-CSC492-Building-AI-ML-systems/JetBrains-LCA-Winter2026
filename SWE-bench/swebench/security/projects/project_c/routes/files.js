const express = require("express");
const path = require("path");
const fs = require("fs");
const router = express.Router();
const { requireAuth } = require("../middleware/auth");

const FILES_DIR = path.join(__dirname, "..", "public", "files");

// CWE-22: Path traversal — filename from URL parameter is joined without normalization.
// An attacker can use "../../../etc/passwd" to read arbitrary files on the server.
router.get("/api/files/:filename", requireAuth, (req, res) => {
  const filePath = path.join(FILES_DIR, req.params.filename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: "File not found" });
  }
  return res.sendFile(filePath);
});

module.exports = router;
