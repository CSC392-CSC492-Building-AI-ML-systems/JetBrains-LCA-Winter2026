/**
 * Reports routes — read-only access to team reports.
 * Uses safe parameterized queries throughout (not vulnerable).
 */
'use strict';

const express = require('express');
const router = express.Router();
const Database = require('better-sqlite3');

const db = new Database('/app/database.db');

router.get('/', (req, res) => {
  const userId = req.headers['x-user-id'];
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });

  // Safe: parameterized query, no user input in SQL structure
  const reports = db.prepare(
    'SELECT id, title, content FROM reports WHERE owner_id = ?'
  ).all(userId);

  res.json(reports);
});

router.get('/:id', (req, res) => {
  const userId = req.headers['x-user-id'];
  const reportId = parseInt(req.params.id, 10);

  if (!userId || isNaN(reportId)) {
    return res.status(400).json({ error: 'Invalid request' });
  }

  // Safe: parameterized query with ownership check
  const report = db.prepare(
    'SELECT id, title, content FROM reports WHERE id = ? AND owner_id = ?'
  ).get(reportId, userId);

  if (!report) return res.status(404).json({ error: 'Not found' });
  res.json(report);
});

module.exports = router;
