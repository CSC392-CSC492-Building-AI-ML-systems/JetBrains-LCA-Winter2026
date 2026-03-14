"use strict";
const express = require("express");
const path = require("path");
const fs = require("fs");

const { validateMiddleware } = require("./middleware/validate");
const uploadRouter = require("./routes/upload");
const adminRouter = require("./routes/admin");
const authRouter = require("./routes/auth");

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(validateMiddleware);

app.use(uploadRouter);
app.use(adminRouter);
app.use(authRouter);

// Ensure uploads directory exists
const UPLOAD_DIR = path.join(__dirname, "uploads");
if (!fs.existsSync(UPLOAD_DIR)) {
    fs.mkdirSync(UPLOAD_DIR);
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, "0.0.0.0", () => {
    console.log(`Project F listening on port ${PORT}`);
});

module.exports = app;
