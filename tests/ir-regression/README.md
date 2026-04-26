# IR regression examples

These examples exercise cases that require the TACKY-style IR lowering in `compile.py`.
Each `.c` file has generated `.s`, `.memh`, and `.memb` outputs beside it.

Expected return values when run from `main`:

- `nested-expr.c`: 10, proves nested binary subexpressions preserve both sides.
- `dynamic-array-store.c`: 7, proves computed array addresses do not clobber RHS values.
- `nested-calls.c`: 9, proves nested call results are saved before the outer call.
- `ptr-and-for.c`: 3, proves pointer-based calls work with `for (int i = ...)`.
