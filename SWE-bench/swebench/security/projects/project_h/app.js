'use strict';

const express = require('express');
const app = express();

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Security middleware — applied to most routes
const { validateInput } = require('./middleware/input');
const { setSecurityHeaders } = require('./security/headers');
const { rateLimiter } = require('./security/ratelimit');

app.use(setSecurityHeaders);
app.use(rateLimiter);
app.use(validateInput);

// Routes
const authRouter = require('./routes/auth');
const settingsRouter = require('./routes/settings');
const paymentRouter = require('./routes/payment');
const reportsRouter = require('./routes/reports');

app.use('/auth', authRouter);
app.use('/settings', settingsRouter);
app.use('/payment', paymentRouter);
app.use('/reports', reportsRouter);

app.get('/health', (req, res) => res.json({ status: 'ok' }));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));

module.exports = app;
