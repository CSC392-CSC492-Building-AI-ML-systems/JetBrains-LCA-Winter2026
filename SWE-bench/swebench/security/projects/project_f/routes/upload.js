"use strict";
const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");

const router = express.Router();
const UPLOAD_DIR = path.join(__dirname, "..", "uploads");

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, UPLOAD_DIR),
    filename: (req, file, cb) => cb(null, Date.now() + "-" + file.originalname),
});

// BUG (CWE-434): multer is configured with no fileFilter — no extension check,
// no MIME type check. An attacker can upload a .php, .js, or .html file that
// could be executed or served by the web server.
const upload = multer({ storage });   // line 17 — no fileFilter

router.post("/upload", upload.single("file"), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: "No file" });
    }
    res.json({ filename: req.file.filename });
});

module.exports = router;
