// Feature: if/else branch with >= relational operator.
// Expected return: 7 (then-branch taken because a >= 1)

int g;

int main() {
    int a = 1;

    if (a >= 1) {
        g = 7;
    } else {
        g = 3;
    }

    return g;
}
