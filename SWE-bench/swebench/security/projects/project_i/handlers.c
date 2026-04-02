/* handlers.c — log ingestion and export request handlers */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <syslog.h>

#include "server.h"

/* Simple key extractor: finds "key":"value" in a JSON string */
static int json_get_str(const char *json, const char *key,
                        char *out, size_t out_size)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":\"", key);
    const char *p = strstr(json, search);
    if (!p) return -1;
    p += strlen(search);
    size_t i = 0;
    while (*p && *p != '"' && i < out_size - 1)
        out[i++] = *p++;
    out[i] = '\0';
    return (int)i;
}

static int json_get_int(const char *json, const char *key)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    const char *p = strstr(json, search);
    if (!p) return 0;
    p += strlen(search);
    return atoi(p);
}

/*
 * handle_log_ingest — parse a JSON log batch and record each entry.
 *
 * Expected JSON format:
 *   { "count": N, "entries": [ { "path": "...", "user_agent": "...", ... } ] }
 */
int handle_log_ingest(const char *json_body, size_t body_len)
{
    (void)body_len;

    int count = json_get_int(json_body, "count");
    if (count <= 0 || count > MAX_ENTRIES)
        return -1;

    /*
     * CWE-190: integer overflow — count * sizeof(log_entry_t) wraps when
     * count is large enough (e.g. count == 0x10000001 on 32-bit size_t),
     * causing malloc to allocate a tiny buffer while the loop writes beyond it.
     */
    log_entry_t *entries = malloc(count * sizeof(log_entry_t));
    if (!entries) return -1;

    /* Parse each entry from the JSON array */
    const char *cursor = strstr(json_body, "\"entries\"");
    if (!cursor) { free(entries); return -1; }

    for (int i = 0; i < count; i++) {
        memset(&entries[i], 0, sizeof(log_entry_t));
        json_get_str(cursor, "path",       entries[i].path,       MAX_PATH_LEN);
        json_get_str(cursor, "method",     entries[i].method,     sizeof(entries[i].method));
        json_get_str(cursor, "user_agent", entries[i].user_agent, MAX_AGENT_LEN);
        entries[i].status_code = json_get_int(cursor, "status");
        entries[i].bytes_sent  = (uint32_t)json_get_int(cursor, "bytes");
        entries[i].timestamp   = (uint32_t)json_get_int(cursor, "ts");

        /*
         * CWE-134: format string vulnerability — user_agent is passed as the
         * format string to syslog.  An attacker-controlled "%n%s%s%s%s%x" in
         * the User-Agent field can read/write arbitrary memory.
         */
        syslog(LOG_INFO, entries[i].user_agent);   /* format string injection */

        /* Advance cursor past the current entry */
        const char *next = strstr(cursor + 1, "{");
        if (next) cursor = next;
    }

    free(entries);
    return 0;
}

/*
 * handle_export — write all stored log entries to the given output path.
 */
void handle_export(const char *output_path)
{
    FILE *f = fopen(output_path, "w");
    if (!f) return;
    fprintf(f, "# Log export\n");
    fclose(f);
}
