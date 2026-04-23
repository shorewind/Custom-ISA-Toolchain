// Regression: control-flow labels must stay unique across nested branches.

int g;
int main() {
	int i = 0;
	int s = 0;
	if (i == 0) {
		s = 1;
	} else {
		s = 2;
	}
	while (i < 2) {
		i = i + 1;
	}
	for (i = 0; i < 2; i = i + 1) {
		if (s != 0) {
			s = s + 1;
		} else {
			s = s - 1;
		}
	}
	g = s;
	return g;
}
