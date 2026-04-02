/**
 * Input validation helpers.
 * Provides schema-based validation using manual checks.
 */
'use strict';

function isValidUsername(username) {
  if (typeof username !== 'string') return false;
  if (username.length < 3 || username.length > 32) return false;
  return /^[a-zA-Z0-9_]+$/.test(username);
}

function isValidEmail(email) {
  if (typeof email !== 'string') return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isValidPassword(password) {
  if (typeof password !== 'string') return false;
  return password.length >= 8;
}

function sanitizeString(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/[<>"']/g, '').trim();
}

module.exports = { isValidUsername, isValidEmail, isValidPassword, sanitizeString };
