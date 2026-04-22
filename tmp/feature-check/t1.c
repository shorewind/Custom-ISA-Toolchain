int g;

int main() {
	int a = 5;
	int b = 2;

	g = (a - b) & (a | b);
	return g;
}
