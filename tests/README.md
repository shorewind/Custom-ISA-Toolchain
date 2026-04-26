# Test Layout

The `tests/` tree mixes artifact fixtures with executable semantic checks. The
split is intentional: some regressions are easiest to see by inspecting emitted
assembly, while others are only obvious when the generated machine code runs.

## Directory roles

- `tests/basic/`: smallest hand-checkable example pair for the compiler and assembler.
- `tests/feature-check/`: broad smoke coverage for the supported language surface, further split into `expressions/`, `arrays/`, `control-flow/`, and `calls/`.
- `tests/ir-regression/`: focused cases that specifically stress IR lowering and evaluation order, further split into `expressions/`, `arrays/`, and `calls/`.
- `tests/label-check/`: control-flow label uniqueness sanity checks.
- `tests/test_compiler.py`: semantic unit tests that compile, assemble, and execute programs in-process.

## How the unit tests work

`tests/test_compiler.py` is an end-to-end harness, not a pure parser-only test.
Each semantic test follows the same pipeline:

1. `compile_to_asm(src)` lexes, parses, and code-generates custom assembly.
2. `assemble_text(asm)` runs the real assembler passes and returns a memory image plus symbols.
3. `run_words(mem, start_pc=...)` executes that memory image in a tiny Python interpreter for the ISA.
4. `run_source(src)` wraps the whole pipeline and returns the final `r1` value as the function result.

That means the unit tests validate the integrated behavior of:

- the lexer and parser
- IR lowering
- assembly generation
- assembler symbol resolution and encoding
- runtime behavior of the emitted code

This file is named `test_compiler.py`, but in practice it tests the compiler
pipeline plus enough assembler and ISA semantics to catch codegen regressions.

## When to add which kind of test

- Add or update `tests/test_compiler.py` when the important question is "does this program still behave correctly?"
- Add or update `tests/feature-check/` when the important question is "what exact assembly or memory image does this feature produce?" Put the fixture under the closest category subdirectory.
- Add or update `tests/ir-regression/` when the bug involves nested expressions, temporaries, call ordering, pointer plumbing, or dynamic array addressing. Put the fixture under the closest category subdirectory.
- Add or update `tests/label-check/` when you are validating branch-label generation rather than full program behavior.

## Recommended testing workflow

Run the semantic harness first:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

Then inspect or regenerate fixture outputs for the affected examples if a
change touches emitted assembly format or memory layout.
