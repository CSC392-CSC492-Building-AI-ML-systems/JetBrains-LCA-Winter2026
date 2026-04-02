/**
 * User settings routes.
 * GET  /settings       — retrieve user settings
 * POST /settings/merge — merge partial settings update
 */
'use strict';

const express = require('express');
const router = express.Router();
const Database = require('better-sqlite3');

const db = new Database('/app/database.db');

/**
 * Deep-merge src into dst recursively.
 * CWE-1321: no guard against __proto__ or constructor keys — enables prototype pollution.
 */
function deepMerge(dst, src) {
  for (const key of Object.keys(src)) {
    // Missing check: if (key === '__proto__' || key === 'constructor') continue;
    if (src[key] && typeof src[key] === 'object' && !Array.isArray(src[key])) {
      dst[key] = dst[key] || {};
      deepMerge(dst[key], src[key]);  // CWE-1321: recursive merge without __proto__ guard
    } else {
      dst[key] = src[key];
    }
  }
  return dst;
}

router.get('/', (req, res) => {
  const userId = req.headers['x-user-id'];
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });
  const user = db.prepare('SELECT settings FROM users WHERE id = ?').get(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  try {
    res.json(JSON.parse(user.settings || '{}'));
  } catch {
    res.json({});
  }
});

router.post('/merge', (req, res) => {
  const userId = req.headers['x-user-id'];
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });

  const user = db.prepare('SELECT settings FROM users WHERE id = ?').get(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });

  let current = {};
  try { current = JSON.parse(user.settings || '{}'); } catch {}

  // User-supplied update merged directly — __proto__ key causes prototype pollution
  const updated = deepMerge(current, req.body);

  db.prepare('UPDATE users SET settings = ? WHERE id = ?')
    .run(JSON.stringify(updated), userId);

  res.json({ status: 'updated', settings: updated });
});

module.exports = router;
