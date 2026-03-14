const express = require("express");
const session = require("express-session");

const usersRouter = require("./routes/users");
const filesRouter = require("./routes/files");
const fetchRouter = require("./routes/fetch");
const adminRouter = require("./routes/admin");

const app = express();

app.use(express.json());
app.use(
  session({
    secret: process.env.SESSION_SECRET || "dev-secret",
    resave: false,
    saveUninitialized: false,
  })
);

app.use(usersRouter);
app.use(filesRouter);
app.use(fetchRouter);
app.use(adminRouter);

const PORT = process.env.PORT || 3000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = app;
