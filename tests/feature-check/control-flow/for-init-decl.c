// Feature: for loop with int declaration in the init clause.
// Expected return: 3 (loop body runs for i=0, i=1, i=2; s increments each time)

int main() {
    int s = 0;

    for (int i = 0; i < 3; i = i + 1) {
        s = s + 1;
    }

    return s;
}
