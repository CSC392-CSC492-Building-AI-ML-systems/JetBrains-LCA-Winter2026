/* main.c — HTTP log ingestion server entry point */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "server.h"

#define RECV_BUFSIZE 65536

static void handle_connection(int client_fd)
{
    char buf[RECV_BUFSIZE];
    ssize_t n = recv(client_fd, buf, sizeof(buf) - 1, 0);
    if (n <= 0) {
        close(client_fd);
        return;
    }
    buf[n] = '\0';

    /* Minimal HTTP parsing: find double-CRLF separating headers from body */
    char *body = strstr(buf, "\r\n\r\n");
    if (body) {
        body += 4;
        size_t body_len = (size_t)(n - (body - buf));

        if (strstr(buf, "POST /ingest") != NULL) {
            int result = handle_log_ingest(body, body_len);
            const char *resp = result == 0
                ? "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                : "HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n";
            send(client_fd, resp, strlen(resp), 0);
        } else if (strstr(buf, "GET /export") != NULL) {
            handle_export("/tmp/export.log");
            const char *resp = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n";
            send(client_fd, resp, strlen(resp), 0);
        } else {
            const char *resp = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n";
            send(client_fd, resp, strlen(resp), 0);
        }
    }
    close(client_fd);
}

int main(void)
{
    auth_result_t auth = authenticate();
    if (!auth.is_admin) {
        fprintf(stderr, "Access denied: admin required\n");
        return 1;
    }
    printf("Authenticated as: %s\n", auth.username);

    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) { perror("socket"); return 1; }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(SERVER_PORT),
        .sin_addr.s_addr = INADDR_ANY,
    };
    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); return 1;
    }
    listen(server_fd, 5);
    printf("Log ingestion server listening on port %d\n", SERVER_PORT);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t addrlen = sizeof(client_addr);
        int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &addrlen);
        if (client_fd < 0) continue;
        handle_connection(client_fd);
    }
    return 0;
}
