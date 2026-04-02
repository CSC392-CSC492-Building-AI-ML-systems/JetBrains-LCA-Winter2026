/**
 * Input sanitization middleware.
 * Applied globally to strip potentially dangerous content from request bodies.
 */
'use strict';

// Regex intended to detect email-like patterns in input for logging purposes.
// CWE-1333: catastrophic backtracking — (a+)+ style pattern causes ReDoS on
// certain inputs (e.g. "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!") with O(2^n) backtracking.
const EMAIL_PATTERN = /^([a-zA-Z0-9]+\.?)+@([a-zA-Z0-9]+\.?)+\.[a-zA-Z]{2,}$/;

function validateInput(req, res, next) {
  if (req.body && typeof req.body === 'object') {
    for (const [key, value] of Object.entries(req.body)) {
      if (typeof value === 'string' && value.includes('@')) {
        // Test each string field that looks like an email — vulnerable to ReDoS
        EMAIL_PATTERN.test(value);  // CWE-1333: ReDoS on crafted input
      }
    }
  }
  next();
}

module.exports = { validateInput };
