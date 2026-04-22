int bump(int &x) {
    x = x + 1;
    return x;
}

int main() {
    int s = 0;

    for (int i = 0; i < 3; i = i + 1) {
        bump(s);
    }

    return s;
}
