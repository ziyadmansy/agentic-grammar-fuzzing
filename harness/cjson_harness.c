#include <stdio.h>
#include <stdlib.h>

#include "cJSON.h"

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
    const char *parse_end = NULL;
    unsigned char *input = read_stdin(&length);
    cJSON *document;

    if (input == NULL) {
        fputs("status=internal_error\n", stderr);
        return 2;
    }

    document = cJSON_ParseWithLengthOpts((const char *)input, length + 1,
                                         &parse_end, 1);
    if (document == NULL) {
        size_t offset = parse_end == NULL ? 0 : (size_t)(parse_end - (const char *)input);
        printf("status=rejected offset=%zu\n", offset);
        free(input);
        return 0;
    }

    puts("status=accepted");
    cJSON_Delete(document);
    free(input);
    return 0;
}