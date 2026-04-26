# IR regression examples

These examples exercise cases that require the TACKY-style IR lowering in `compile.py`.
Each `.c` file has generated `.s`, `.memh`, and `.memb` outputs beside it.

The fixtures are grouped by the backend pressure they create:

- `expressions/`: nested expression evaluation order.
- `arrays/`: computed-address stores and loads.
- `calls/`: nested calls and pointer-mutating calls interacting with control flow.

Expected return values when run from `main`:

- `expressions/nested-expr.c`: 10, proves nested binary subexpressions preserve both sides.
- `arrays/dynamic-array-store.c`: 7, proves computed array addresses do not clobber RHS values.
- `calls/nested-calls.c`: 9, proves nested call results are saved before the outer call.
- `calls/ptr-and-for.c`: 3, proves pointer-based calls work with `for (int i = ...)`.
