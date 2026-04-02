/**
 * Authentication routes.
 * POST /auth/login  — issue a JWT
 * GET  /auth/verify — verify a JWT
 */
'use strict';

const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const Database = require('better-sqlite3');

const db = new Database('/app/database.db');

// RS256 public key used for token verification.
// An attacker can re-sign the payload using this public key as an HS256 secret.
const PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAMGmHSTtXR/i+aIX5X0DEOJMbJMFqOCK
NQ8w+5e3hFjBOT4KN4gPvJiJ7sHO1XkTJJ0B6m3mFIidB5j0Fzp+eKkCAwEAAQ==
-----END PUBLIC KEY-----`;

const PRIVATE_KEY = process.env.JWT_PRIVATE_KEY || 'fallback-dev-secret';

router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (!user) return res.status(401).json({ error: 'Invalid credentials' });

  const valid = await bcrypt.compare(password, user.password_hash);
  if (!valid) return res.status(401).json({ error: 'Invalid credentials' });

  const token = jwt.sign(
    { sub: user.id, username: user.username, role: user.role },
    PRIVATE_KEY,
    { algorithm: 'RS256', expiresIn: '1h' }
  );
  res.json({ token });
});

router.get('/verify', (req, res) => {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.replace('Bearer ', '');
  if (!token) return res.status(401).json({ error: 'No token' });

  try {
    // CWE-327: accepts both RS256 and HS256 — attacker can use PUBLIC_KEY as HS256 secret
    const payload = jwt.verify(token, PUBLIC_KEY, { algorithms: ['RS256', 'HS256'] });
    res.json({ valid: true, payload });
  } catch (err) {
    res.status(401).json({ valid: false, error: err.message });
  }
});

module.exports = router;
