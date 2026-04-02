/* auth.c — simple username/password authentication for the admin interface */
#include <stdio.h>
#include <string.h>

#include "server.h"

/* Credentials stored in a config file — not hardcoded in source */
#define CREDENTIALS_FILE "/etc/logserver/credentials"

static int load_credentials(char *username_out, char *password_out)
{
    FILE *f = fopen(CREDENTIALS_FILE, "r");
    if (!f) {
        /* Fall back to default credentials if config file is missing */
        strncpy(username_out, "admin",   MAX_USERNAME - 1);
        strncpy(password_out, "changeme", MAX_PASSWORD - 1);
        return 0;
    }
    /* File format: first line = username, second line = password */
    if (fgets(username_out, MAX_USERNAME, f) == NULL) {
        fclose(f); return -1;
    }
    /* Strip trailing newline */
    username_out[strcspn(username_out, "\n")] = '\0';

    if (fgets(password_out, MAX_PASSWORD, f) == NULL) {
        fclose(f); return -1;
    }
    password_out[strcspn(password_out, "\n")] = '\0';
    fclose(f);
    return 0;
}

/*
 * authenticate — prompt for username and password on stdin.
 *
 * CWE-676: gets() is used to read the password from stdin.  gets() performs
 * no bounds checking and will overflow the fixed-size input buffer when the
 * user supplies more than MAX_PASSWORD-1 characters, enabling a stack buffer
 * overflow that can overwrite the return address or adjacent variables.
 */
auth_result_t authenticate(void)
{
    auth_result_t result = { .username = {0}, .is_admin = 0 };

    char stored_user[MAX_USERNAME] = {0};
    char stored_pass[MAX_PASSWORD] = {0};
    if (load_credentials(stored_user, stored_pass) != 0) {
        fprintf(stderr, "Failed to load credentials\n");
        return result;
    }

    char input_user[MAX_USERNAME];
    char input_pass[MAX_PASSWORD];

    printf("Username: ");
    fflush(stdout);
    if (fgets(input_user, sizeof(input_user), stdin) == NULL) return result;
    input_user[strcspn(input_user, "\n")] = '\0';

    printf("Password: ");
    fflush(stdout);
    /* CWE-676: gets() has no length limit — stack buffer overflow if input > MAX_PASSWORD-1 */
    gets(input_pass);   /* dangerous function: use fgets(input_pass, sizeof(input_pass), stdin) */

    if (strcmp(input_user, stored_user) == 0 &&
        strcmp(input_pass, stored_pass) == 0) {
        strncpy(result.username, input_user, MAX_USERNAME - 1);
        result.is_admin = 1;
    }
    return result;
}
