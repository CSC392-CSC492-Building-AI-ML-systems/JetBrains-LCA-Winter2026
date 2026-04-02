FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN make

# Create log directories and a stub credentials file
RUN mkdir -p /var/log/app /etc/logserver && \
    echo "admin" > /etc/logserver/credentials && \
    echo "password123" >> /etc/logserver/credentials

EXPOSE 8080
CMD ["./logserver"]
