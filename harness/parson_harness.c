#include <stdio.h>
#include <stdlib.h>

#include "parson.h"

static unsigned char *read_stdin(size_t *length) {
    size_t capacity = 4096;
    size_t used = 0;
    unsigned char *buffer = malloc(capacity + 1);

    if (buffer == NULL) {
        return NULL;
    }

    while (!feof(stdin)) {
        size_t available = capacity - used;
        size_t count = fread(buffer + used, 1, available, stdin);
        used += count;
        if (ferror(stdin)) {
            free(buffer);
            return NULL;
        }
        if (used == capacity && !feof(stdin)) {
            unsigned char *grown;
            capacity *= 2;
            grown = realloc(buffer, capacity + 1);
            if (grown == NULL) {
                free(buffer);
                return NULL;
            }
            buffer = grown;
        }
    }

    buffer[used] = '\0';
    *length = used;
    return buffer;
}

int main(void) {
    size_t length;
    unsigned char *input = read_stdin(&length);
    JSON_Value *value;

    if (input == NULL) {
        fputs("status=internal_error\n", stderr);
        return 2;
    }

    value = json_parse_string((const char *)input);
    if (value == NULL) {
        puts("status=rejected");
        free(input);
        return 0;
    }

    puts("status=accepted");
    json_value_free(value);
    free(input);
    return 0;
}
