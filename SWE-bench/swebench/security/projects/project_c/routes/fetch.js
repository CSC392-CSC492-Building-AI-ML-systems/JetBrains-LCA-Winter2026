const express = require("express");
const axios = require("axios");
const router = express.Router();
const { requireAuth } = require("../middleware/auth");

// CWE-918: SSRF — user-supplied URL is passed directly to axios.get() with no validation.
// An attacker can make the server send requests to internal services (e.g. http://169.254.169.254/
// for AWS metadata) or other systems not intended to be accessible.
router.post("/api/fetch", requireAuth, async (req, res) => {
  const { url } = req.body;
  if (!url) {
    return res.status(400).json({ error: "url is required" });
  }
  try {
    const response = await axios.get(url);
    return res.json({ status: response.status, data: response.data });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
});

module.exports = router;
