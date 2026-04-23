// Feature: global array declaration, write and read with constant index.
// Expected return: a[0] + a[1] = 1 + 2 = 3

int g;
int a[2];

int main() {
    a[0] = 1;
    a[1] = 2;

    g = a[0] + a[1];
    return g;
}
