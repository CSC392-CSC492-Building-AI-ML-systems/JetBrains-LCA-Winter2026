FROM node:20-slim

WORKDIR /app
COPY package.json .
RUN npm install

COPY . .

RUN node init_db.js

EXPOSE 3000
CMD ["node", "app.js"]
