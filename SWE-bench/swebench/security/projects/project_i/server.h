/* server.h — shared types and constants for the log ingestion server */
#ifndef SERVER_H
#define SERVER_H

#include <stdint.h>
#include <stddef.h>

#define MAX_PATH_LEN    256
#define MAX_AGENT_LEN   512
#define MAX_CMD_LEN     512
#define MAX_USERNAME    64
#define MAX_PASSWORD    64
#define LOG_BUFFER_SIZE 4096
#define MAX_ENTRIES     1024
#define SERVER_PORT     8080

typedef struct {
    uint32_t timestamp;
    char     path[MAX_PATH_LEN];
    char     method[8];
    int      status_code;
    uint32_t bytes_sent;
    char     user_agent[MAX_AGENT_LEN];
} log_entry_t;

typedef struct {
    char username[MAX_USERNAME];
    int  is_admin;
} auth_result_t;

/* handlers.c */
int  handle_log_ingest(const char *json_body, size_t body_len);
void handle_export(const char *output_path);

/* utils.c */
int  run_log_command(const char *log_type, const char *date_filter);
void compress_logs(const char *archive_name);

/* auth.c */
auth_result_t authenticate(void);

#endif /* SERVER_H */
