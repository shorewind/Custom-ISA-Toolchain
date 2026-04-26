// Regression: nested calls must preserve intermediate return values.

int inc(int x) {
    return x + 1;
}

int add(int x, int y) {
    return x + y;
}

int main() {
    int a = 3;
    return add(inc(a), inc(4));
}
