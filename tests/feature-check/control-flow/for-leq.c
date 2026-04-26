// Feature: for loop with <= relational operator and explicit init/update.
// Expected return: 1 (s takes i's last value before loop exits; i reaches 2)

int g;

int main() {
    int i = 0;
    int s = 0;

    for (i = 0; i <= 1; i = i + 1) {
        s = i;
    }

    g = s;
    return g;
}
