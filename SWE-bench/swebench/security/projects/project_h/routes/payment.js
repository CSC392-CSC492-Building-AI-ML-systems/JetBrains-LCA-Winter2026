/**
 * Payment processing routes.
 * POST /payment/charge — process a payment for the authenticated user
 * GET  /payment/history — list payment history
 *
 * NOTE: The CSRF protection middleware in security/csrf.js is defined but
 * NOT applied here, leaving this state-changing endpoint unprotected.
 */
'use strict';

const express = require('express');
const router = express.Router();
const Database = require('better-sqlite3');

const db = new Database('/app/database.db');

// The CSRF middleware exists but is intentionally NOT imported here
// const { verifyCsrfToken } = require('../security/csrf');

// CWE-352: CSRF — POST endpoint with no CSRF token validation
router.post('/charge', (req, res) => {
  const userId = req.headers['x-user-id'];
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });

  const { amount, description } = req.body;
  if (!amount || isNaN(parseFloat(amount))) {
    return res.status(400).json({ error: 'Valid amount required' });
  }

  db.prepare(
    'INSERT INTO payments (user_id, amount, description) VALUES (?, ?, ?)'
  ).run(userId, parseFloat(amount), description || '');

  res.json({ status: 'charged', amount: parseFloat(amount) });
});

router.get('/history', (req, res) => {
  const userId = req.headers['x-user-id'];
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });

  const payments = db.prepare(
    'SELECT id, amount, description FROM payments WHERE user_id = ? ORDER BY id DESC'
  ).all(userId);

  res.json(payments);
});

module.exports = router;
