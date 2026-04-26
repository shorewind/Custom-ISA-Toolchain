int result;

int func() {
    return 42;
}

int main() {
    int a = 10;
    int b = 3;
    int c;

    c = a + b;
    result = c;

    if (result != 0) {
        c = func();
    } else {
        c = 99;
    }

    return c;
}