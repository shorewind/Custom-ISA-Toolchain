# Custom-ISA-Toolchain

A small C-subset compiler and assembler for a custom 16-bit instruction set architecture. The compiler translates a deliberately limited C-like language into custom assembly; the assembler resolves labels and emits a small proof-of-concept memory image suitable for `$readmemh`-style hardware loading.

The implementation follows the same broad design direction as Nora Sandler's *Writing a C Compiler*: lex and parse into an AST, lower into a simple TACKY-style three-address intermediate representation, then emit assembly. TACKY means tiny, abstract, computer-like kernel, and IR means intermediate representation. TACKY is the lowering layer that makes evaluation order explicit by breaking nested expressions into small, single-step instructions before code generation.

## Quick Start

Compile C to assembly:

```sh
python3 compile.py tests/basic/c-example.c tests/basic/assembly-example.s
```

Assemble custom assembly to a hex memory image:

```sh
python3 assemble.py tests/basic/assembly-example.s tests/basic/imem-example.memh
```

Run regression tests:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

Inspect the test layout:

```sh
sed -n '1,240p' tests/README.md
```

## Repository Map

- `compile.py`: C-subset compiler, including lexer, parser, AST, IR lowering, and custom assembly generation.
- `assemble.py`: two-pass assembler for `.text`, `.data`, labels, instructions, and `.word` data.
- `tests/basic/`: minimal checked example source, assembly, and memory images.
- `tests/feature-check/`: broad fixture-style smoke tests covering the supported surface area, grouped into `expressions/`, `arrays/`, `control-flow/`, and `calls/`.
- `tests/ir-regression/`: focused examples proving nested expressions, dynamic array stores, nested calls, and pointer-based calls, grouped into `expressions/`, `arrays/`, and `calls/`.
- `tests/label-check/`: control-flow label sanity check.
- `tests/test_compiler.py`: semantic unit tests that compile source, assemble it, and execute it in a tiny ISA interpreter.
- `tests/README.md`: guide to how the test directories fit together.

## Test Strategy

The repository uses two complementary test styles:

- Fixture tests under `tests/basic/`, `tests/feature-check/`, `tests/ir-regression/`, and `tests/label-check/`.
- Semantic unit tests in `tests/test_compiler.py`.

The fixture tests are file-based. They keep `.c`, generated `.s`, and generated memory images side by side so you can inspect backend output directly after changes.

The unit tests are behavior-based. They take a small C-subset program, run it through the compiler and assembler in-process, then execute the resulting machine words in a tiny interpreter that models the custom ISA. This is the fast path for catching semantic regressions such as register clobbering, bad lowering order, broken call plumbing, and incorrect pointer or array behavior.

In short:

- Use fixture tests when you want to inspect emitted artifacts.
- Use unit tests when you want to assert meaning, not formatting.

## Supported C Subset

The compiler intentionally supports a compact subset of C, centered on `int` values and structured control flow.

Supported declarations:

```c
int x;
int x = expression;
int a[10];
```

Supported assignments:

```c
x = expression;
a[i] = expression;
```

Supported expressions:

- Integer literals, expected to fit the ISA's immediate/data model.
- Scalar variables.
- Array indexing, such as `a[i]`.
- Function calls, such as `inc(x)`.
- Unary negation, represented internally as `0 - expr`.
- Binary `+`, `-`, `&`, and `|`.

Supported control flow:

```c
if (condition) { ... } else { ... }
while (condition) { ... }
for (init; condition; update) { ... }
```

Supported condition operators:

```c
==  !=  <  <=  >  >=
```

Supported functions:

```c
int inc(int x) {
    return x + 1;
}

int bump(int *x) {
    *x = *x + 1;
    return *x;
}
```

## Unsupported C Features

This is not a full C compiler. These are intentionally unsupported:

- Types other than `int`.
- `void`, `char`, `long`, `unsigned`, strings, structs, and general pointers.
- General pointer arithmetic, except the internal address handling used for arrays and pointer parameters.
- `break`, `continue`, `switch`, `do while`, `goto`, and ternary expressions.
- Relational operators as value-producing expressions, such as `x = a < b;`.
- Function prototypes, separate translation units, includes, and preprocessing.
- Block-scoped shadowing. Duplicate locals in a function are rejected.
- Recursion and reentrant calls.
- Array bounds checking.

## Compiler Architecture

`compile.py` is intentionally organized as a simple pipeline.

### 1. Lexing

The lexer strips `//` comments and tokenizes identifiers, integer literals, punctuation, arithmetic/bitwise operators, and relational operators.

Output shape:

```text
source text -> list[str] tokens
```

### 2. Parsing and AST

The parser is a hand-written recursive descent parser. It builds dataclass-based AST nodes for declarations, expressions, conditions, assignments, statements, functions, and programs.

Expression precedence is handled with layered parse functions:

```text
parse_expr
  -> parse_or
  -> parse_and
  -> parse_add_sub
  -> parse_unary
  -> parse_primary / parse_postfix
```

### 3. TACKY-Style IR Lowering

The AST is lowered into a simple three-address intermediate representation before assembly generation. In practice, this means the compiler turns nested expressions into a sequence of tiny assignments so that each intermediate value is named and preserved.

The IR uses simple values:

```text
int constant | scalar slot name
```

Complex operations become explicit instructions, for example:

```text
t0 = a + b
t1 = c + d
g = t0 + t1
```

This avoids the main correctness problem of direct recursive AST-to-register codegen: nested expression evaluation can otherwise clobber registers holding earlier subresults.

The compiler also performs a small practical optimization: if an expression is assigned directly to a scalar destination, the final result is written straight to that destination instead of going through a temporary. For example, `c = a + b;` emits one add and one store to `c`, not `main_t0` plus a second store.

### 4. Symbol and Storage Layout

The backend allocates global variables, locals, parameters, pointer slots, and IR temporaries into `.data` labels.

In other words, named program storage lives in memory, not in registers. A
variable such as `a`, `g`, `main_t0`, or `bump_p_ptr_x` gets a `.data` label
and is loaded into a register only when an instruction needs it. Registers are
used as short-lived working state during code generation; they are not the
home location of source-level variables.

As a small convenience optimization, compile-time constant local initializers
in `main` may be written directly into the initial `.data` image instead of
being emitted as runtime `LDI`/`ST` setup code. Non-constant initializers, and
initializers in other functions, are still lowered as normal runtime code.

This choice is simple and matches the current ISA constraints, but it has consequences:

- No runtime stack is required.
- No stack pointer is required.
- Function calls use statically allocated parameter slots.
- Recursion and reentrant calls are not supported.

### 5. Assembly Generation

The assembly generator lowers each IR instruction into custom ISA assembly using a small scratch-register convention:

- `r0`: hardwired zero by convention. Used as the base register for symbolic data accesses such as `main_a(r0)`, and for unconditional branches written as `BEZ r0, label`.
- `r1`: primary value register. Holds the left operand for binary operations and the final function return value.
- `r2`: secondary value register. Holds the right operand for binary operations and computed array indices.
- `r3`: general result/store scratch register. Receives ALU results, temporary loaded values, compare results for conditional branches, and staged call arguments before they are written to parameter slots.
- `r4`: computed array-element address register for dynamic array loads and stores.
- `r5`: pointer/address scratch register. Used to load helper addresses such as `addr_a`, and to dereference pointer parameters for `*x` loads and stores.
- `r6`: currently unused by the compiler. Reserved as extra scratch space for future address-heavy or pointer-heavy code generation.
- `r7`: link register for `JL`/`JR` calls. Functions that make nested calls save and restore it through a statically allocated `.data` slot.

Control flow lowers to labels and branches. Function calls store argument values into callee parameter slots, execute `JL r7, callee`, and read the return value from `r1`.

This means the current compiler uses registers for transient computation only:
operands, ALU results, computed addresses, dereference scratch, the return
value, and the link register. If a value must survive beyond a short instruction
sequence, it is normally written back to its `.data` slot.

## Assembler Architecture

`assemble.py` is a two-pass assembler.

### Assembly Format

The assembler accepts:

```asm
.text
.global main

main:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    ADD   r3, r1, r2
    ST    r3, main_c(r0)
    LD    r1, main_c(r0)
    HALT

.data
main_a: .word 2
main_b: .word 5
main_c: .word 0
```

### First Pass

The first pass:

- Tracks the active section: `.text` or `.data`.
- Assigns word addresses to instructions and `.word` data.
- Builds a symbol table for labels.
- Supports labels on their own line or before content on the same line.

Current default layout:

```text
.text base = 0
.data base = text_base + number of emitted text words
demo memory image = 64 words
actual ISA address space = 1024 words
```

The current layout intentionally keeps the generated image small and easy to inspect for proof-of-concept testing. By default, the assembler places `.data` immediately after the emitted `.text` section so the layout is derived from actual program size rather than a hardcoded boundary.

### Second Pass

The second pass:

- Encodes instructions into 16-bit words.
- Resolves labels in branches, jumps, memory operands, and `.word` directives.
- Emits a unified 64-word memory image in hex.

The assembler supports these instruction groups:

- R-type: `ADD`, `SUB`, `AND`, `OR`, `SLT`, shifts, `HALT`.
- Immediate/load-store: `LDI`, `LD`, `ST`.
- Branches: `BEZ`, `BNZ`.
- Calls/jumps: `JL`, `JR`.

## Examples

Basic compile example:

- Source: `tests/basic/c-example.c`
- Assembly: `tests/basic/assembly-example.s`
- Hex image: `tests/basic/imem-example.memh`
- Binary image: `tests/basic/imem-example.memb`

IR regression examples:

- `tests/ir-regression/expressions/nested-expr.c`: nested expression preservation, expected return `10`.
- `tests/ir-regression/arrays/dynamic-array-store.c`: computed array store preserving RHS value, expected return `7`.
- `tests/ir-regression/calls/nested-calls.c`: nested function calls, expected return `9`.
- `tests/ir-regression/calls/ptr-and-for.c`: pointer-based calls with `for (int i = ...)`, expected return `3`.

## Testing Strategy

The main regression test file is `tests/test_compiler.py`.

It verifies compiler behavior by running the full pipeline in-process:

```text
C source string
  -> compile.py lexer/parser/codegen
  -> assemble.py first/second pass
  -> small ISA interpreter
  -> asserted return value / memory state
```

This catches semantic bugs that plain assembly snapshot tests can miss, including register-clobbering errors in nested expressions and dynamic array stores.

## Known Limitations and Hardware Notes

The generated assembly includes `.global main`, but the assembler currently records labels only; it does not insert startup code. If hardware always starts executing at address `0`, either emit `main` first or add a startup jump/call to `main`.

The current 64-word demo memory image means larger programs can still collide with data or exceed the available space. For larger examples, the assembler memory depth should become configurable.

## References

- Nora Sandler, *Writing a C Compiler*, No Starch Press, 2024: https://nostarch.com/writing-c-compiler
- O'Reilly listing and table of contents for *Writing a C Compiler*: https://www.oreilly.com/library/view/writing-a-c/9781098182229/
- Compiler implementation: `compile.py`
- Assembler implementation: `assemble.py`
- Semantic regression tests: `tests/test_compiler.py`
- IR regression examples: `tests/ir-regression/README.md`
