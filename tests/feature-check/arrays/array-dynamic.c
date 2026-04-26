// Feature: array write and read with a variable (dynamic) index expression.
// Expected return: 9 (a[i+1] written and read back through a computed address)

int a[4];

int main() {
    int i = 1;

    a[i + 1] = 9;
    return a[i + 1];
}
