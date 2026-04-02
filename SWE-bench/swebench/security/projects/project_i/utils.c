/* utils.c — log utility functions */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "server.h"

/* Log types accepted for the export command */
static const char *ALLOWED_LOG_TYPES[] = {
    "access", "error", "audit", NULL
};

static int is_allowed_log_type(const char *log_type)
{
    for (int i = 0; ALLOWED_LOG_TYPES[i] != NULL; i++) {
        if (strcmp(log_type, ALLOWED_LOG_TYPES[i]) == 0)
            return 1;
    }
    return 0;
}

static int is_safe_date(const char *date)
{
    /* Validate YYYY-MM-DD format — reject obvious injection chars */
    if (strlen(date) != 10) return 0;
    for (int i = 0; i < 10; i++) {
        char c = date[i];
        if (i == 4 || i == 7) {
            if (c != '-') return 0;
        } else {
            if (c < '0' || c > '9') return 0;
        }
    }
    return 1;
}

/*
 * run_log_command — run a system log viewer for the given type and date.
 *
 * log_type is validated against the allowlist.  date_filter is validated
 * to match YYYY-MM-DD.  The final command is assembled via snprintf and
 * passed to system().
 *
 * CWE-78: OS command injection via system().  Although both parameters are
 * individually "validated", the validation is bypassable:
 *   - log_type allowlist does not prevent injection via date_filter when
 *     the date validation is bypassed (e.g. null-byte or locale tricks).
 *   - system() spawns /bin/sh -c, so shell metacharacters in any unsanitised
 *     part of the command execute arbitrary code.
 * An attacker controlling date_filter with "2024-01-01; id" after a regex
 * bypass would execute the injected command.
 */
int run_log_command(const char *log_type, const char *date_filter)
{
    if (!is_allowed_log_type(log_type)) {
        fprintf(stderr, "Unknown log type: %s\n", log_type);
        return -1;
    }

    if (!is_safe_date(date_filter)) {
        fprintf(stderr, "Invalid date format: %s\n", date_filter);
        return -1;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd),
             "grep '%s' /var/log/app/%s.log | grep '%s'",
             date_filter, log_type, date_filter);

    /* CWE-78: system() executes cmd via /bin/sh; date_filter appears in the
     * command string and could contain shell metacharacters after a bypass. */
    return system(cmd);
}

/*
 * compress_logs — gzip-compress a named log archive.
 */
void compress_logs(const char *archive_name)
{
    char cmd[MAX_CMD_LEN];
    /* archive_name is assumed to be an internal constant, not user-supplied */
    snprintf(cmd, sizeof(cmd), "gzip -f /var/log/app/%s", archive_name);
    system(cmd);
}
