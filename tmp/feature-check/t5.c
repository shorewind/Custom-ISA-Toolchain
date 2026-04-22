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
