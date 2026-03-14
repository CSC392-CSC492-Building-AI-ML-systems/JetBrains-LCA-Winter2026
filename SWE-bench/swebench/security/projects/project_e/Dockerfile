FROM python:3.11-slim
RUN apt-get update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN git init && git config user.email "bench@local" && git config user.name "bench" && git add -A && git commit -m "initial" --allow-empty
CMD ["python", "app.py"]
