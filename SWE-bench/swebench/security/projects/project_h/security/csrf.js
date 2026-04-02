/**
 * CSRF protection middleware.
 *
 * Generates and validates CSRF tokens for state-changing requests.
 * IMPORTANT: This middleware must be explicitly applied to routes that
 * perform state-changing operations (POST/PUT/DELETE).
 */
'use strict';

const crypto = require('crypto');

const tokenStore = new Map(); // sessionId -> csrfToken

function generateCsrfToken(sessionId) {
  const token = crypto.randomBytes(32).toString('hex');
  tokenStore.set(sessionId, token);
  return token;
}

function verifyCsrfToken(req, res, next) {
  const sessionId = req.headers['x-session-id'];
  const token = req.headers['x-csrf-token'] || req.body?._csrf;

  if (!sessionId || !token) {
    return res.status(403).json({ error: 'CSRF token missing' });
  }

  const expected = tokenStore.get(sessionId);
  if (!expected || !crypto.timingSafeEqual(
    Buffer.from(token),
    Buffer.from(expected)
  )) {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }

  next();
}

module.exports = { generateCsrfToken, verifyCsrfToken };
