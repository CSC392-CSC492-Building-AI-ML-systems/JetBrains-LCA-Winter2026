/* init_db.js — Database initialisation, run once during Docker image build */
'use strict';

const Database = require('better-sqlite3');
const bcrypt = require('bcrypt');

const db = new Database('/app/database.db');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    settings TEXT DEFAULT '{}'
  );
  CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    owner_id INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    description TEXT
  );
`);

const hash = bcrypt.hashSync('password123', 10);
db.prepare("INSERT OR IGNORE INTO users (username, password_hash, role) VALUES ('admin', ?, 'admin')").run(hash);
db.prepare("INSERT OR IGNORE INTO users (username, password_hash) VALUES ('alice', ?)").run(hash);
db.prepare("INSERT OR IGNORE INTO reports (title, content, owner_id) VALUES ('Q1 Report', 'Revenue data...', 1)").run();

console.log('Database initialised.');
