/**
 * Rate limiter middleware.
 * Limits each IP to 100 requests per 15-minute window.
 */
'use strict';

const requestCounts = new Map();
const WINDOW_MS = 15 * 60 * 1000; // 15 minutes
const MAX_REQUESTS = 100;

function rateLimiter(req, res, next) {
  const ip = req.ip || req.socket.remoteAddress;
  const now = Date.now();
  const entry = requestCounts.get(ip);

  if (!entry || now - entry.start > WINDOW_MS) {
    requestCounts.set(ip, { count: 1, start: now });
    return next();
  }

  entry.count++;
  if (entry.count > MAX_REQUESTS) {
    return res.status(429).json({ error: 'Too many requests' });
  }
  next();
}

module.exports = { rateLimiter };
