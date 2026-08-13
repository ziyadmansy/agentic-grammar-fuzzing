#include <stdlib.h>

int main(void) {
    int *p = malloc(4);
    p[2] = 1;
    free(p);
    return 0;
}