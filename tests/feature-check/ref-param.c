// Feature: C++ by-reference parameter (int &x); compiler implicitly takes the
// address of the argument and dereferences on every access inside the callee.
// Expected return: 5
// Note: int &x syntax is C++ only; for C-compatible code use int *x (see ptr-param.c).

int bump(int &x) {
    x = x + 1;
    return x;
}

int main() {
    int a = 4;
    bump(a);
    return a;
}
