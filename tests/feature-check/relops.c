// Feature: relational operators ==, !=, and >.
// Expected return: 3 (all three conditions are true, r increments once each)

int g;

int main() {
    int a = 3;
    int b = 5;
    int r = 0;

    if (a == 3) {
        r = r + 1;
    }
    if (a != b) {
        r = r + 1;
    }
    if (b > a) {
        r = r + 1;
    }

    g = r;
    return g;
}
