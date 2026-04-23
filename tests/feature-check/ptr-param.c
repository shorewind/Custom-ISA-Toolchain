// Feature: C pass-by-pointer (int *x); caller passes &a, callee uses *x to
// read and write through the pointer.
// Expected return: 5 (a incremented in place via pointer)

int bump(int *x) {
    *x = *x + 1;
    return *x;
}

int main() {
    int a = 4;
    bump(&a);
    return a;
}
