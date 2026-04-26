// Feature: global variable; binary operators +, -, &, |.
// Expected return: (5 - 2) & (5 | 2) = 3 & 7 = 3

int g;

int main() {
    int a = 5;
    int b = 2;

    g = (a - b) & (a | b);
    return g;
}
