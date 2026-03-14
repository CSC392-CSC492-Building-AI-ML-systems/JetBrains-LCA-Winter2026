FROM node:18-slim
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN apt-get update && apt-get install -y git iputils-ping --no-install-recommends && rm -rf /var/lib/apt/lists/*
RUN git init && git config user.email "bench@local" && git config user.name "bench" && git add -A && git commit -m "initial" --allow-empty
CMD ["node", "app.js"]
