// Feature: while loop with < relational operator; accumulator pattern.
// Expected return: 0 + 1 = 1 (loop runs for i=0 then i=1, exits when i=2)

int g;

int main() {
    int i = 0;
    int s = 0;

    while (i < 2) {
        s = s + i;
        i = i + 1;
    }

    g = s;
    return g;
}
