// Feature: function call with pass-by-value parameter.
// Expected return: 4 (a is unchanged in caller; pass-by-value copies the argument)

int g;

int inc(int x) {
    x = x + 1;
    return x;
}

int main() {
    int a = 4;

    g = inc(a);
    return a;
}
