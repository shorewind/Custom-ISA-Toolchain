# Feature Check Coverage

These examples are broad smoke tests for the compiler's supported C subset.
Each `.c` file has generated `.s`, `.memh`, and `.memb` outputs beside it so
changes in parsing, IR lowering, code generation, or assembly encoding can be
inspected directly.

The fixtures are grouped by surface area:

- `expressions/`: scalar arithmetic and bitwise expressions.
- `arrays/`: constant-index and computed-index array access.
- `control-flow/`: relational tests plus `if`, `while`, and `for`.
- `calls/`: pass-by-value and pointer-based call plumbing.

This set is comprehensive in the practical sense that it touches every major
language feature and backend path the toolchain currently claims to support:

- Scalar declarations, initialization, globals, and arithmetic/bitwise ops.
- `if/else`, `while`, and `for` control flow.
- All supported relational operators across the suite.
- Static and computed array indexing.
- Function calls by value and by pointer.
- Address-taking, dereference load/store, and return-value plumbing.

It is not exhaustive for all combinations. The dedicated semantic regression
tests in `tests/test_compiler.py` and the focused IR cases in
`tests/ir-regression/` still matter for catching evaluation-order bugs and
other corner cases.

## Per-test purpose

- `expressions/arithmetic.c`: proves scalar locals/global storage plus `+`, `-`, `&`, and `|`.
- `arrays/array-static.c`: proves constant-index array store/load code paths.
- `arrays/array-dynamic.c`: proves computed index lowering and address arithmetic.
- `control-flow/if-else-geq.c`: proves conditional branching with `>=`.
- `control-flow/while-lt.c`: proves loop back-edges with `<`.
- `control-flow/for-leq.c`: proves `for` lowering with explicit init/update and `<=`.
- `control-flow/for-init-decl.c`: proves `for (int i = ...)` declaration handling.
- `control-flow/relops.c`: proves repeated conditional lowering for `==`, `!=`, and `>`.
- `calls/value-param.c`: proves pass-by-value call setup does not mutate the caller.
- `calls/ptr-param.c`: proves C-style pointer parameter passing with `&x` and `*x`.

## Why this is enough for the supported subset

Together, these tests cover every currently advertised source construct at
least once, and the risky backend cases more than once:

- Storage: globals, locals, arrays, params, and temporaries.
- Addressing: direct scalar loads/stores, helper-based address loads, and
  computed array element addresses.
- Control flow: straight-line execution, one-way branches, two-way branches,
  loop headers, loop exits, and loop-carried variable updates.
- Calls: argument passing, return values, and indirect mutation of caller data.

If all feature-check cases still compile to sensible assembly and memory
images, the toolchain is usually structurally intact. If semantic behavior also
matches expectations under `tests/test_compiler.py`, the supported subset is
covered with reasonable confidence.
